"""
T4 - Gaussian sharpening of Theorem 3 (verification of the SHIPPED statement).

SHIPPED STATEMENT (supplementary S14.4 / theory/bayesian_source_reliability.tex):

    With linear read-out and equal-covariance Gaussian P_1, P_2 separated along
    a rank-1 channel direction with projected standard deviation sigma,

        alpha_star = Phi(Delta_nb / (2 sigma))            [Gaussian-exact]

    At Delta_nb = 1.8 (the non-Bayesian residual log-odds gap) and
    sigma in [2.2, 4.5] (late-layer projected sd for a 3-to-8B transformer),

        alpha_star in [0.579, 0.659]                       [numeric range]

    General sub-Gaussian companion (proxy variance sigma^2), via the standard
    Hoeffding/Chernoff bound on the midpoint-threshold classifier
    (per-class error P(X - mu >= Delta/2) <= exp(-Delta^2/(8 sigma^2))):

        alpha_star >= 1 - exp(-Delta_nb^2 / (8 sigma^2))   [companion, auxiliary]

    NOTE: the 1/2-weighted variant of the companion that appeared in an earlier
    draft is NOT valid for general sub-Gaussian laws (Rademacher violates it);
    the audit corrected the constant. The companion is auxiliary: the shipped
    theorem statement is the Gaussian-exact form plus the numeric range, and
    the PASS verdict below gates on those alone.

REVISION HISTORY (documented discovery, retained for the audit trail):
    The original draft stated a LINEAR bound alpha_star >= 1/2 + Delta_nb/(4 sigma),
    citing Tsybakov 2009 §2.6. SymPy and NumPy refuted that form: the Gaussian
    Bayes accuracy Phi(z/2) has slope 1/(2 sqrt(2 pi)) ~= 0.199 < 1/4 at z = 0,
    and the cited result supports an upper bound via Pinsker, not a lower bound.
    The shipped statement above replaces it. Section R below re-runs the
    refutation so the discovery remains reproducible.

Verifier design (two-grader-equivalence standard):
    - SymPy  : Cauchy-Schwarz + rank-1 reduction; Bayes-optimal threshold for
               equal-covariance Gaussians is the midpoint; exact accuracy
               identity alpha_star = 1/2 + erf(z / (2 sqrt 2)) / 2 = Phi(z/2);
               monotonicity in sigma; numeric range endpoints at Delta_nb = 1.8.
    - NumPy  : Monte-Carlo equality witness alpha_sim ~= Phi(z/2) (two-sided,
               binomial tolerance) across random configurations and a d=32
               rank-1 witness; range endpoints at sigma = 2.2 and 4.5;
               Hoeffding companion across three sub-Gaussian families.
    - Z3     : Cauchy-Schwarz at d = 2, 3, 4 (UNSAT on negation) + rank-1
               reduction. Phi/erf/exp are outside Z3's decidable theory; scope
               documented (N/A on the transcendental step, as in T7).

Random seed 42 throughout. Run: ``python proof.py``.
"""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path

import numpy as np
import sympy as sp
import z3
from scipy.stats import norm


SEED = 42
HERE = Path(__file__).resolve().parent
LOG_PATH = HERE / "verification_log.txt"

DELTA_NB = 1.8          # non-Bayesian residual log-odds gap (S14.3)
SIGMA_LO, SIGMA_HI = 2.2, 4.5
RANGE_LO, RANGE_HI = 0.579, 0.659   # alpha_star = Phi(Delta_nb/(2 sigma)) endpoints, 3 dp


class Tee:
    def __init__(self, path: Path) -> None:
        self.fh = open(path, "w", encoding="utf-8")

    def write(self, msg: str) -> None:
        sys.__stdout__.write(msg)
        self.fh.write(msg)

    def flush(self) -> None:
        sys.__stdout__.flush()
        self.fh.flush()

    def close(self) -> None:
        self.fh.close()


def hr() -> None:
    print("-" * 78)


# ---------------------------------------------------------------------------
# Sub-Gaussian samplers (for the companion bound)
# ---------------------------------------------------------------------------

def sample_gaussian(n: int, mu: float, sigma: float, rng: np.random.Generator) -> np.ndarray:
    return rng.normal(loc=mu, scale=sigma, size=n)


def sample_rademacher(n: int, mu: float, sigma: float, rng: np.random.Generator) -> np.ndarray:
    """mu + sigma * Rademacher. Sub-Gaussian with proxy variance exactly sigma^2."""
    return mu + sigma * (2 * rng.integers(0, 2, size=n) - 1)


def sample_uniform(n: int, mu: float, sigma: float, rng: np.random.Generator) -> np.ndarray:
    """mu + Uniform(-sqrt(3) sigma, sqrt(3) sigma); bounded, proxy variance sigma^2."""
    a = math.sqrt(3) * sigma
    return mu + rng.uniform(-a, a, size=n)


# ---------------------------------------------------------------------------
# Verifier 1 - SymPy symbolic
# ---------------------------------------------------------------------------

def verify_sympy() -> bool:
    print("[SymPy] symbolic verification of the SHIPPED Gaussian-exact statement")

    # Step A: Cauchy-Schwarz (foundational, used in the rank-1 reduction).
    w1, w2, mu1, mu2 = sp.symbols("w1 w2 mu1 mu2", real=True)
    inner = w1 * mu1 + w2 * mu2
    cs_diff = sp.expand((w1**2 + w2**2) * (mu1**2 + mu2**2) - inner**2)
    cs_ok = sp.simplify(cs_diff - (w1 * mu2 - w2 * mu1) ** 2) == 0
    print(f"  Step A Cauchy-Schwarz residual is a perfect square: {cs_ok}")

    # Step B: rank-1 reduction ||c * v_star|| = |c| for unit v_star.
    c = sp.symbols("c", positive=True)
    v1s, v2s = sp.symbols("v1 v2", real=True)
    norm_sq = sp.simplify((c * v1s) ** 2 + (c * v2s) ** 2 - c**2 * (v1s**2 + v2s**2))
    rank1_ok = norm_sq == 0
    print(f"  Step B rank-1 reduction ||c v||^2 = c^2 ||v||^2: {rank1_ok}")

    # Step C: Bayes-optimal threshold for equal-covariance Gaussians is the
    # midpoint. Log-likelihood ratio is linear in x and zero at (m1 + m2)/2.
    x, m1, m2, sig = sp.symbols("x m1 m2 sigma", real=True)
    sig = sp.symbols("sigma", positive=True)
    llr = (-(x - m1) ** 2 + (x - m2) ** 2) / (2 * sig**2)
    llr_simpl = sp.simplify(llr)
    root = sp.solve(sp.Eq(llr_simpl, 0), x)
    midpoint_ok = len(root) == 1 and sp.simplify(root[0] - (m1 + m2) / 2) == 0
    print(f"  Step C Bayes threshold equals midpoint (m1 + m2)/2: {midpoint_ok}")

    # Step D: exact accuracy. With threshold at the midpoint, the per-class
    # correct probability is P(N(0, sigma^2) < Delta/2) and the balanced
    # accuracy is Phi(Delta / (2 sigma)). Verify by symbolic integration.
    Delta = sp.symbols("Delta", positive=True)
    pdf = sp.exp(-(x**2) / (2 * sig**2)) / (sig * sp.sqrt(2 * sp.pi))
    p_correct = sp.integrate(pdf, (x, -sp.oo, Delta / 2))
    z = Delta / sig
    phi_form = sp.Rational(1, 2) + sp.erf(z / (2 * sp.sqrt(2))) / 2
    diff = sp.simplify((p_correct - phi_form).rewrite(sp.erf))
    exact_ok = diff == 0 or diff.equals(0) is True
    print(f"  Step D exact accuracy integral equals Phi(z/2) (erf form): {exact_ok}")

    # Step E: monotonicity in sigma (accuracy strictly decreasing in sigma).
    dalpha_dsigma = sp.diff(phi_form.subs(Delta, DELTA_NB), sig)
    mono_ok = sp.simplify(dalpha_dsigma) < 0  # symbolic sign at positive sigma
    try:
        mono_ok = bool(sp.ask(sp.Q.negative(dalpha_dsigma), sp.Q.positive(sig)))
    except Exception:
        mono_ok = bool(float(dalpha_dsigma.subs(sig, 3.0)) < 0)
    print(f"  Step E d alpha / d sigma < 0 (accuracy decreasing in sigma): {mono_ok}")

    # Step F: numeric range endpoints at Delta_nb = 1.8.
    alpha_at = lambda s: float(phi_form.subs({Delta: DELTA_NB, sig: s}))
    a_hi_sigma = alpha_at(SIGMA_HI)   # sigma = 4.5 -> lower endpoint
    a_lo_sigma = alpha_at(SIGMA_LO)   # sigma = 2.2 -> upper endpoint
    print(f"  Step F alpha(sigma={SIGMA_HI}) = {a_hi_sigma:.6f} (shipped lower endpoint {RANGE_LO})")
    print(f"          alpha(sigma={SIGMA_LO}) = {a_lo_sigma:.6f} (shipped upper endpoint {RANGE_HI})")
    range_ok = (round(a_hi_sigma, 3) == RANGE_LO) and (round(a_lo_sigma, 3) == RANGE_HI)
    print(f"  Step F shipped 3-dp endpoints match recomputation: {range_ok}")

    ok = cs_ok and rank1_ok and midpoint_ok and exact_ok and mono_ok and range_ok
    print(f"  [SymPy verdict] shipped Gaussian-exact statement: {ok}")
    return ok


# ---------------------------------------------------------------------------
# Verifier 2 - NumPy numerical witness
# ---------------------------------------------------------------------------

def verify_numpy(n_per_channel: int = 200_000, n_configs: int = 8) -> bool:
    """Monte-Carlo equality witness for alpha_star = Phi(z/2) (two-sided check
    within binomial tolerance), range endpoints, d=32 rank-1 witness, and the
    Hoeffding companion across three sub-Gaussian families."""
    print(f"[NumPy] Monte-Carlo equality witness, n_per_channel={n_per_channel}")
    rng = np.random.default_rng(SEED)

    # (a) Gaussian equality across random configurations: |alpha_sim - Phi(z/2)|
    # within 5 binomial sds.
    eq_fail = 0
    print("  k   sigma   Delta    z      alpha_sim   Phi(z/2)   |diff|/sd")
    for k in range(n_configs):
        sigma = float(rng.uniform(0.5, 4.0))
        Delta = float(rng.uniform(0.1, 2.0))
        mu1 = float(rng.uniform(-1, 1))
        mu2 = mu1 + Delta
        x1 = sample_gaussian(n_per_channel, mu1, sigma, rng)
        x2 = sample_gaussian(n_per_channel, mu2, sigma, rng)
        thr = 0.5 * (mu1 + mu2)
        alpha_sim = (np.sum(x1 < thr) + np.sum(x2 > thr)) / (2 * n_per_channel)
        z = Delta / sigma
        alpha_phi = norm.cdf(z / 2)
        sd = math.sqrt(alpha_phi * (1 - alpha_phi) / (2 * n_per_channel))
        nsd = abs(alpha_sim - alpha_phi) / sd
        print(f"  {k:02d}  {sigma:6.3f} {Delta:6.3f}  {z:5.3f}  {alpha_sim:9.5f}  {alpha_phi:9.5f}  {nsd:6.2f}")
        if nsd > 5:
            eq_fail += 1
    eq_ok = eq_fail == 0
    print(f"  (a) Gaussian equality holds within 5 binomial sds: {eq_ok}")

    # (b) Range endpoints at Delta_nb = 1.8.
    print()
    endpoint_ok = True
    for sigma, shipped in [(SIGMA_HI, RANGE_LO), (SIGMA_LO, RANGE_HI)]:
        x1 = sample_gaussian(n_per_channel, 0.0, sigma, rng)
        x2 = sample_gaussian(n_per_channel, DELTA_NB, sigma, rng)
        thr = DELTA_NB / 2
        alpha_sim = (np.sum(x1 < thr) + np.sum(x2 > thr)) / (2 * n_per_channel)
        alpha_phi = norm.cdf(DELTA_NB / (2 * sigma))
        ok = abs(alpha_sim - alpha_phi) < 0.005 and round(alpha_phi, 3) == shipped
        endpoint_ok &= ok
        print(f"  (b) sigma={sigma}: alpha_sim={alpha_sim:.5f}, Phi={alpha_phi:.5f}, shipped={shipped}, ok={ok}")

    # (c) d=32 rank-1 witness.
    d, sigma_d, Delta_d, n_d = 32, 2.0, 1.0, 100_000
    v_star = rng.normal(size=d)
    v_star /= np.linalg.norm(v_star)
    X1 = rng.normal(scale=sigma_d, size=(n_d, d))
    X2 = rng.normal(scale=sigma_d, size=(n_d, d)) + Delta_d * v_star
    proj1, proj2 = X1 @ v_star, X2 @ v_star
    thr = 0.5 * Delta_d
    alpha_d = (np.sum(proj1 < thr) + np.sum(proj2 > thr)) / (2 * n_d)
    alpha_d_phi = norm.cdf(Delta_d / (2 * sigma_d))
    d_ok = abs(alpha_d - alpha_d_phi) < 0.005
    print(f"  (c) d=32 rank-1: alpha_sim={alpha_d:.5f} vs Phi(z/2)={alpha_d_phi:.5f}, ok={d_ok}")

    # (d) AUXILIARY: Hoeffding companion across sub-Gaussian families. Correct
    # constant: per-class error <= exp(-Delta^2/(8 sigma^2)) (no 1/2 factor;
    # the 1/2-weighted variant fails for Rademacher and was corrected by the
    # audit). Not part of the shipped statement; reported, not gating.
    print()
    comp_fail = 0
    for fam_name, sampler in [("gaussian", sample_gaussian),
                              ("rademacher", sample_rademacher),
                              ("uniform-bounded", sample_uniform)]:
        for _ in range(4):
            sigma = float(rng.uniform(0.5, 3.0))
            Delta = float(rng.uniform(0.2, 2.0))
            x1 = sampler(50_000, 0.0, sigma, rng)
            x2 = sampler(50_000, Delta, sigma, rng)
            thr = Delta / 2
            alpha_sim = (np.sum(x1 < thr) + np.sum(x2 > thr)) / 100_000
            bound = 1 - math.exp(-(Delta / sigma) ** 2 / 8)
            tol = 5 * math.sqrt(max(alpha_sim * (1 - alpha_sim), 1e-9) / 100_000)
            if alpha_sim < bound - tol:
                comp_fail += 1
                print(f"  (d) VIOLATION {fam_name}: alpha={alpha_sim:.5f} < bound={bound:.5f}")
    comp_ok = comp_fail == 0
    print(f"  (d) [auxiliary] Hoeffding companion (corrected constant) holds on "
          f"12/12 sub-Gaussian configurations: {comp_ok}")

    ok = eq_ok and endpoint_ok and d_ok
    print(f"[NumPy verdict] shipped statement (a)+(b)+(c): {ok}   "
          f"[auxiliary companion: {comp_ok}]")
    return ok


# ---------------------------------------------------------------------------
# Verifier 3 - Z3 SMT (foundational steps; transcendental N/A)
# ---------------------------------------------------------------------------

def verify_z3() -> bool:
    print("[Z3] SMT counter-model search for Cauchy-Schwarz at d=2, 3, 4")
    for d in [2, 3, 4]:
        s = z3.Solver()
        s.set("timeout", 60_000)
        a = z3.RealVector("a", d)
        b = z3.RealVector("b", d)
        inner = sum(a[i] * b[i] for i in range(d))
        s.add(sum(a[i] ** 2 for i in range(d)) * sum(b[i] ** 2 for i in range(d)) - inner * inner < 0)
        res = s.check()
        print(f"  d={d}: Z3 check (CS violation) = {res}")
        if res != z3.unsat:
            return False

    s_r = z3.Solver()
    s_r.set("timeout", 60_000)
    c_sym, v0, v1 = z3.Real("c"), z3.Real("v0"), z3.Real("v1")
    s_r.add(v0**2 + v1**2 == 1)
    s_r.add((c_sym * v0) ** 2 + (c_sym * v1) ** 2 != c_sym**2)
    res_r = s_r.check()
    print(f"  rank-1 reduction (||c v||^2 != c^2 with ||v||=1): {res_r}")
    if res_r != z3.unsat:
        return False

    print("  Gaussian-exact accuracy (Phi/erf) outside Z3's decidable theory;")
    print("  covered by SymPy (exact integration) + NumPy (Monte-Carlo equality).")
    print("[Z3] PASS=True (foundational Cauchy-Schwarz + rank-1 reduction)")
    return True


# ---------------------------------------------------------------------------
# Section R - reproducible refutation of the SUPERSEDED linear form
# ---------------------------------------------------------------------------

def refute_superseded_linear_form() -> None:
    print("[Section R] superseded linear bound alpha_star >= 1/2 + z/4 (historical)")
    for zv in [0.1, 0.5, 1.0, 2.0]:
        phi = norm.cdf(zv / 2)
        lin = 0.5 + zv / 4
        print(f"  z={zv:4.1f}: Phi(z/2)={phi:.5f}, 1/2 + z/4={lin:.5f}, margin={phi - lin:+.5f}")
    print("  margin < 0 at z >= 0.5: the superseded linear form is REFUTED")
    print("  (slope of Phi(z/2) at z=0 is 1/(2 sqrt(2 pi)) ~= 0.199 < 1/4).")
    print("  The shipped Gaussian-exact statement replaces it; this section is")
    print("  retained so the proof-pipeline discovery remains reproducible.")


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def main() -> int:
    tee = Tee(LOG_PATH)
    sys.stdout = tee
    try:
        print("T4 - Gaussian sharpening (SHIPPED Gaussian-exact statement)")
        print("   alpha_star = Phi(Delta_nb / (2 sigma));  Delta_nb = 1.8,")
        print(f"   sigma in [{SIGMA_LO}, {SIGMA_HI}]  =>  alpha_star in [{RANGE_LO}, {RANGE_HI}]")
        print("   companion: alpha_star >= 1 - exp(-Delta_nb^2 / (8 sigma^2))")
        print(f"   seed={SEED}, time={time.strftime('%Y-%m-%d %H:%M:%S')}")
        hr()

        ok_sym = verify_sympy()
        hr()
        ok_num = verify_numpy()
        hr()
        ok_z3 = verify_z3()
        hr()
        refute_superseded_linear_form()
        hr()

        passed = sum([ok_sym, ok_num])
        print("VERIFIER COVERAGE on the SHIPPED statement:")
        print(f"  SymPy={ok_sym} NumPy={ok_num}  ({passed}/2 applicable; "
              f"Z3 foundational={ok_z3}, transcendental N/A)")
        print()
        if passed == 2 and ok_z3:
            print("THEOREM 4 STATUS: PASS (shipped Gaussian-exact statement verified")
            print("  by 2/2 applicable verifiers; Z3 covers the foundational steps;")
            print("  superseded linear form documented as refuted in Section R)")
            return 0
        print("THEOREM 4 STATUS: FAIL")
        return 1
    finally:
        sys.stdout = sys.__stdout__
        tee.close()


if __name__ == "__main__":
    sys.exit(main())
