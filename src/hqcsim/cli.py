from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from .metrics import summarize
from .models import PacketType
from .simpy_engine import LinkConfig, run_sim
from .traffic import generate_packets
from .schedulers.credit_event import CreditEventScheduler, CreditState
from .schedulers.time_gate import GateCycle, TimeGateScheduler


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="hqcsim", description="Hybrid QC Scheduler Simulator")
    sub = p.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="Run a simulation scenario")
    run.add_argument("--seed", type=int, default=None, help="Random seed (optional)")
    run.add_argument("--t-end", type=float, default=5.0)
    run.add_argument("--classical-lam", type=float, default=800.0)
    run.add_argument("--quantum-lam", type=float, default=120.0)
    run.add_argument("--service-time", type=float, default=0.001)
    run.add_argument("--loss-prob", type=float, default=0.0)
    run.add_argument("--policy", choices=["gate", "credit", "fair-credit"], default="credit")

    # gate policy params
    run.add_argument("--gate-cycle", type=float, default=0.02)
    run.add_argument("--gate-quantum", type=float, default=0.006)
    run.add_argument("--gate-classical", type=float, default=0.010)

    # credit policy params
    run.add_argument("--credits-capacity", type=int, default=200)
    run.add_argument("--credits-init", type=int, default=0)

    # credit generation
    run.add_argument("--qutip", action="store_true", help="Use QuTiP quantum link emulator")
    run.add_argument("--distance-km", type=float, default=10.0)
    run.add_argument("--attenuation-db-per-km", type=float, default=0.2)
    run.add_argument("--coupling-eff", type=float, default=0.7)
    run.add_argument("--detector-eff", type=float, default=0.8)
    run.add_argument("--memory-t2", type=float, default=0.2)
    run.add_argument("--use-threshold", action="store_true")
    run.add_argument("--prop-delay-per-km", type=float, default=5e-6)
    run.add_argument("--herald-rtt-factor", type=float, default=1.0)
    run.add_argument("--attempt-rate", type=float, default=200.0)
    run.add_argument("--depolarizing-p", type=float, default=0.02)
    run.add_argument("--success-threshold", type=float, default=0.85)
    run.add_argument("--credit-tick", type=float, default=0.01, help="Seconds between credit updates")
    run.add_argument("--stochastic-credit-rate", type=float, default=80.0, help="credits/sec if not using QuTiP")

    return p


def main() -> None:
    import random
    import time
    args = _build_parser().parse_args()

    if args.cmd == "run":
        t_end: float = args.t_end
        seed = args.seed if args.seed is not None else int(time.time_ns() % (2**32))
        rng = random.Random(seed)
        # traffic
        classical = generate_packets(PacketType.CLASSICAL, args.classical_lam, t_end, seed=rng.randint(0, 10**9), start_id=0)
        quantum = generate_packets(PacketType.QUANTUM_KEY, args.quantum_lam, t_end, seed=rng.randint(0, 10**9), start_id=1_000_000)

        link = LinkConfig(service_time_s=args.service_time, loss_prob=args.loss_prob)

        # scheduler
        credit_state = None
        quantum_credit_consume = None
        if args.policy == "gate":
            gate = GateCycle(args.gate_cycle, args.gate_quantum, args.gate_classical)
            scheduler = TimeGateScheduler(gate)

        elif args.policy == "fair-credit":
            credit_state = CreditState(capacity=args.credits_capacity, credits=args.credits_init)

            from .schedulers.fair_credit import FairCreditScheduler, FairParams

            scheduler = FairCreditScheduler(
                credit_state,
                FairParams(quantum_every_n=5)
            )

            def quantum_credit_consume(n: int) -> bool:
                return credit_state.consume(n)

        else:
            credit_state = CreditState(capacity=args.credits_capacity, credits=args.credits_init)
            scheduler = CreditEventScheduler(credit_state)

            def quantum_credit_consume(n: int) -> bool:
                return credit_state.consume(n)

        # credit generator
        last_update = {"t": 0.0}

        if args.policy == "credit":
            if args.qutip:
                from .qutip_link import QuTiPQuantumLink, QuantumLinkConfig

                qlink = QuTiPQuantumLink(
                    QuantumLinkConfig(
                        attempt_rate_hz=args.attempt_rate,
                        depolarizing_p=args.depolarizing_p,
                        success_threshold=args.success_threshold,
                        use_threshold=args.use_threshold,
                        distance_km=args.distance_km,
                        attenuation_db_per_km=args.attenuation_db_per_km,
                        coupling_eff=args.coupling_eff,
                        detector_eff=args.detector_eff,
                        memory_T2_s=args.memory_t2 if args.memory_t2 > 0 else None,
                        prop_delay_s_per_km=args.prop_delay_per_km,
                        herald_rtt_factor=args.herald_rtt_factor,
                        seed=rng.randint(0, 10**9),
                    )
                )

                def on_tick(now: float) -> None:
                    if credit_state is None:
                        return
                    if now - last_update["t"] < args.credit_tick:
                        return
                    dt = now - last_update["t"]
                    credit_state.add(qlink.credits_generated_in_interval(dt))
                    last_update["t"] = now

            else:
                # simple robust model: credits per second
                def on_tick(now: float) -> None:
                    if credit_state is None:
                        return
                    if now - last_update["t"] < args.credit_tick:
                        return
                    dt = now - last_update["t"]
                    credit_state.add(int(args.stochastic_credit_rate * dt))
                    last_update["t"] = now
        else:
            def on_tick(now: float) -> None:
                _ = now
                return

        res = run_sim(
            classical=classical,
            quantum=quantum,
            scheduler=scheduler,
            link=link,
            t_end=t_end,
            on_tick=on_tick,
            seed=rng.randint(0, 10**9),
            quantum_credit_consume=quantum_credit_consume,
        )

        summary = summarize(res.delivered, res.dropped, res.latencies, t_end=t_end)
        out = asdict(summary)
        # include a few extra useful fields
        if credit_state is not None:
            out["credits_end"] = credit_state.credits
            out["credits_capacity"] = credit_state.capacity
        print(json.dumps(out, indent=2, sort_keys=True))
