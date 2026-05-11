"""
Paxos 两阶段协议演示脚本

用法（需要先启动 3 个 Acceptor 节点）:
  python demo_paxos.py

演示内容:
  1. 3 个 Acceptor 初始状态都是 None
  2. 第一轮投票 (ID=1, 值="会议通知") → 全部接受
  3. 第二轮投票 (ID=2, 值="可疑邮件") → 全部接受 (2>1)
  4. 尝试用旧 ID=1 再次投票 → 被拒绝！(已承诺更高的2)
  5. 演示多数派: 关闭一个节点，仍能达成共识
"""

import requests
import json
import time

NODES = [
    "http://127.0.0.1:8503",
    "http://127.0.0.1:8504",
    "http://127.0.0.1:8505",
]


def print_state(title=""):
    """打印 3 个 Acceptor 的 Paxos 状态"""
    if title:
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}")
    print(f"  {'Node':<15} {'promised_id':<14} {'accepted_id':<14} {'accepted_value'}")
    print(f"  {'-'*15} {'-'*14} {'-'*14} {'-'*15}")
    for url in NODES:
        try:
            r = requests.get(f"{url}/paxos/state", timeout=3)
            s = r.json()
            print(f"  {s['acceptor_id']:<15} {str(s['promised_id']):<14} {str(s['accepted_id']):<14} {str(s['accepted_value'])}")
        except Exception:
            print(f"  {url.split(':')[-1]:<15} {'OFFLINE':<14}")


def reset_all():
    """重置所有 Acceptor"""
    for url in NODES:
        try:
            requests.post(f"{url}/paxos/reset", timeout=3)
        except Exception:
            pass
    print("  所有 Acceptor 已重置")


def send_prepare(node_url, proposal_id):
    """发送 Prepare 请求"""
    try:
        r = requests.post(f"{node_url}/paxos/prepare",
                         json={"proposal_id": proposal_id, "sender": "demo"},
                         timeout=3)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        pass
    return None


def send_accept(node_url, proposal_id, value):
    """发送 Accept 请求"""
    try:
        r = requests.post(f"{node_url}/paxos/accept",
                         json={"proposal_id": proposal_id, "value": value, "sender": "demo"},
                         timeout=3)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        pass
    return None


def run_paxos_round(proposal_id, value):
    """执行完整的一轮 Paxos"""
    print(f"\n  >>> Phase 1: Prepare (ID={proposal_id})")
    promises = []
    for url in NODES:
        resp = send_prepare(url, proposal_id)
        if resp:
            if resp.get("type") == "promise":
                print(f"      {url.split(':')[-1]} → ✅ Promise")
                promises.append(resp)
            else:
                reason = resp.get('value', resp.get('reason', ''))
                print(f"      {url.split(':')[-1]} → ❌ Reject: {reason}")
        else:
            print(f"      {url.split(':')[-1]} → ⚠️  无响应")

    majority = (len(NODES) // 2) + 1
    if len(promises) < majority:
        print(f"  ✗ Prepare 失败 ({len(promises)}/{len(NODES)} < {majority})")
        return False

    print(f"  ✓ Prepare 成功 ({len(promises)}/{len(NODES)} >= {majority})")

    print(f"\n  >>> Phase 2: Accept (ID={proposal_id}, value={value})")
    accepteds = []
    for url in NODES:
        resp = send_accept(url, proposal_id, value)
        if resp:
            if resp.get("type") == "accepted":
                print(f"      {url.split(':')[-1]} → ✅ Accepted")
                accepteds.append(resp)
            else:
                reason = resp.get('value', resp.get('reason', ''))
                print(f"      {url.split(':')[-1]} → ❌ Reject: {reason}")
        else:
            print(f"      {url.split(':')[-1]} → ⚠️  无响应")

    if len(accepteds) < majority:
        print(f"  ✗ Accept 失败 ({len(accepteds)}/{len(NODES)} < {majority})")
        return False

    print(f"  ✓ Accept 成功 ({len(accepteds)}/{len(NODES)} >= {majority})")
    print(f"  🎯 共识达成！最终值: {value}")
    return True


if __name__ == '__main__':
    print("╔══════════════════════════════════════════════════════╗")
    print("║       Paxos 两阶段提交协议 冲突演示                   ║")
    print("╚══════════════════════════════════════════════════════╝")

    # 初始状态
    reset_all()
    print_state("初始状态：所有 Acceptor 的 promised_id = None")

    # 第一轮投票
    print(f"\n{'='*60}")
    print("  第一轮：Proposer 提议 '会议通知'")
    run_paxos_round(proposal_id=1, value="会议通知")
    print_state("第一轮后：promised_id=1, accepted_id=1")

    # 第二轮：更高的 proposal_id
    print(f"\n{'='*60}")
    print("  第二轮：另一个 Proposer 提议 '可疑邮件' (ID更高=2)")
    run_paxos_round(proposal_id=2, value="可疑邮件")
    print_state("第二轮后：promised_id=2, accepted_id=2")

    # 关键演示：用更低的 ID 重试 → 被拒绝
    print(f"\n{'='*60}")
    print("  ⭐ 关键演示：用旧 ID=1 重新发起 Prepare → 应该被拒绝！")
    print("     因为 Acceptor 已经承诺了更高的 ID=2")
    run_paxos_round(proposal_id=1, value="会议通知")

    print(f"\n{'='*60}")
    print("  结论：Paxos 通过 proposal_id 保证了一致性")
    print("  一旦更高的 ID 被承诺，旧 ID 的提案就会被拒绝")
    print("  这就是 Paxos 两阶段提交协议的核心机制")
    print(f"{'='*60}")
