from hqcsim.schedulers.credit_event import CreditEventScheduler, CreditState
from hqcsim.schedulers.time_gate import GateCycle, TimeGateScheduler


def test_time_gate_prefers_quantum_in_quantum_window():
    gate = GateCycle(cycle_s=0.02, quantum_open_s=0.005, classical_open_s=0.01)
    sched = TimeGateScheduler(gate)
    d = sched.choose(now=0.001, q_len=2, c_len=10)
    assert d.send_quantum and not d.send_classical


def test_credit_scheduler_prefers_classical_if_not_full():
    cs = CreditState(capacity=10, credits=5)
    sched = CreditEventScheduler(cs)
    d = sched.choose(now=0.0, q_len=5, c_len=1)
    assert d.send_classical


def test_credit_scheduler_prefers_quantum_when_full():
    cs = CreditState(capacity=10, credits=10)
    sched = CreditEventScheduler(cs)
    d = sched.choose(now=0.0, q_len=5, c_len=5)
    assert d.send_quantum
