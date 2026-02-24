from __future__ import annotations

import math
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class QuantumLinkConfig:
    # Attempt dynamics
    attempt_rate_hz: float = 200.0

    # Channel / distance model (resource-level, not full optics)
    distance_km: float = 10.0
    attenuation_db_per_km: float = 0.2  # typical telecom fiber order
    coupling_eff: float = 0.7           # source + coupling losses (0..1)
    detector_eff: float = 0.8           # detection efficiency (0..1)

    # Timing model
    prop_delay_s_per_km: float = 5e-6   # ~5 microseconds per km in fiber
    herald_rtt_factor: float = 1.0      # ~one RTT of classical signaling per attempt

    # Noise / quality model
    depolarizing_p: float = 0.02
    memory_T2_s: float | None = 0.2     # if None -> no decoherence penalty

    # How strict you want to be:
    # - If use_threshold=True: success requires fidelity >= success_threshold, then apply channel probability.
    # - If use_threshold=False: success probability scales with fidelity directly (usually smoother).
    use_threshold: bool = False
    success_threshold: float = 0.85

    seed: int = 1


class QuTiPQuantumLink:
    """
    Resource-level entanglement generation model:
      - QuTiP gives a *quality metric* (Bell-state fidelity after depolarizing noise + optional decoherence)
      - Distance/attenuation gives a *success probability* for the attempt
      - Timing introduces an RTT-style wait that can reduce fidelity if memory_T2_s is set
    """

    def __init__(self, cfg: QuantumLinkConfig):
        self.cfg = cfg
        self.rng = random.Random(cfg.seed)

        try:
            import qutip as qt  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "QuTiP is not installed. Install with: pip install -e '.[qutip]'"
            ) from e

        self.qt = qt

        # |Phi+> = (|00> + |11>)/sqrt(2)
        bell = (
            qt.tensor(qt.basis(2, 0), qt.basis(2, 0))
            + qt.tensor(qt.basis(2, 1), qt.basis(2, 1))
        ).unit()
        self.rho_ideal = qt.ket2dm(bell)

        self.X = qt.sigmax()
        self.Y = qt.sigmay()
        self.Z = qt.sigmaz()
        self.I = qt.qeye(2)

    def _depolarize_one_qubit(self, rho, p: float, on_first: bool):
        qt = self.qt
        ops = [
            (self.I, 1 - p),
            (self.X, p / 3),
            (self.Y, p / 3),
            (self.Z, p / 3),
        ]
        out = 0 * rho
        for P, w in ops:
            K = qt.tensor(P, self.I) if on_first else qt.tensor(self.I, P)
            out = out + w * (K * rho * K.dag())
        return out

    def _attempt_quality_fidelity(self, wait_s: float) -> float:
        """Return fidelity of an entangled pair after noise + optional memory decoherence."""
        rho = self.rho_ideal
        p = max(0.0, min(1.0, self.cfg.depolarizing_p))

        # Depolarizing noise on both qubits
        rho = self._depolarize_one_qubit(rho, p, on_first=True)
        rho = self._depolarize_one_qubit(rho, p, on_first=False)

        # Optional decoherence penalty due to waiting (very simple exponential decay model)
        if self.cfg.memory_T2_s and self.cfg.memory_T2_s > 0:
            decay = math.exp(-max(0.0, wait_s) / self.cfg.memory_T2_s)
        else:
            decay = 1.0

        # Fidelity vs ideal Bell state
        fidelity = float((rho * self.rho_ideal).tr().real)
        # Apply decoherence penalty as a quality scaling
        fidelity = max(0.0, min(1.0, fidelity * decay))
        return fidelity

    def _channel_success_prob(self) -> float:
        """Distance-based probability that an attempt yields a heralded pair (resource-level)."""
        L = max(0.0, self.cfg.distance_km)
        alpha = max(0.0, self.cfg.attenuation_db_per_km)

        # Convert dB loss to linear transmissivity
        # total_loss_db = alpha * L
        # transmissivity = 10^(-loss_db/10)
        transmissivity = 10 ** (-(alpha * L) / 10.0)

        hw = max(0.0, min(1.0, self.cfg.coupling_eff)) * max(0.0, min(1.0, self.cfg.detector_eff))

        # For entanglement distribution you may need two photons; keep it simple with one effective factor.
        p = transmissivity * hw
        return max(0.0, min(1.0, p))

    def attempt_once(self) -> bool:
        # RTT-style wait: at least a round-trip (heralding/classical confirmation)
        one_way = self.cfg.distance_km * self.cfg.prop_delay_s_per_km
        wait_s = 2.0 * one_way * max(0.0, self.cfg.herald_rtt_factor)

        fidelity = self._attempt_quality_fidelity(wait_s)
        p_chan = self._channel_success_prob()

        if self.cfg.use_threshold:
            if fidelity < self.cfg.success_threshold:
                return False
            # success still limited by channel
            return self.rng.random() < p_chan

        # Smooth model: success probability scales with fidelity (quality matters continuously)
        p_success = p_chan * fidelity
        return self.rng.random() < p_success

    def credits_generated_in_interval(self, dt_s: float) -> int:
        n_attempts = int(max(0.0, self.cfg.attempt_rate_hz) * max(0.0, dt_s))
        successes = 0
        for _ in range(n_attempts):
            if self.attempt_once():
                successes += 1
        return successes