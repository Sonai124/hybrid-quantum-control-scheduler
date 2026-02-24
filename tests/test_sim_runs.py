from hqcsim.models import PacketType
from hqcsim.simpy_engine import LinkConfig, run_sim
from hqcsim.schedulers.credit_event import CreditEventScheduler, CreditState
from hqcsim.traffic import generate_packets


def test_sim_runs_and_delivers_some_packets():
    t_end = 1.0
    classical = generate_packets(PacketType.CLASSICAL, lam=200, t_end=t_end, seed=1, start_id=0)
    quantum = generate_packets(PacketType.QUANTUM_KEY, lam=50, t_end=t_end, seed=2, start_id=1_000_000)

    credits = CreditState(capacity=50, credits=50)
    sched = CreditEventScheduler(credits)

    def on_tick(now: float) -> None:
        _ = now
        return

    res = run_sim(
        classical=classical,
        quantum=quantum,
        scheduler=sched,
        link=LinkConfig(service_time_s=0.001, loss_prob=0.0),
        t_end=t_end,
        on_tick=on_tick,
        quantum_credit_consume=lambda n: credits.consume(n),
    )
    assert len(res.delivered) > 0
