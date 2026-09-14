# Formal Safety Treatment of the CBF Construction

What can and cannot currently be formally claimed about `aerofleet/safety/cbf_gate.py`'s
Control Barrier Function (CBF) implementation, written precisely rather than asserted. This
document exists because "we implemented 11 constraint functions" is not a safety proof, and a
CBF-literate Q1 reviewer will check the math, not just the code comment.

**Read this before citing a safety guarantee in the paper.** Two genuinely different mechanisms
exist in the codebase under the "CBF" name, with different, real levels of formal support:

1. `evaluate_trajectory()` — discrete-point **verification**, not a continuous guarantee.
2. `run_asif_qp()` — a real, per-timestep **safety filter**, but a simplified one that does not
   yet incorporate system dynamics, so it does not yet satisfy the classical CBF forward-invariance
   theorem in full.

Both are explained below, with exactly what *can* be claimed today and what a rigorous claim
would require.

## 1. Background — the classical CBF guarantee

For a control-affine system `ẋ = f(x) + g(x)u` and a candidate barrier function `h(x)`, `h` is a
valid CBF for the safe set `C = {x : h(x) ≥ 0}` if there exists an extended class-K function `α`
such that, for all `x ∈ C`:

```
sup_u [ ∇h(x)·f(x) + ∇h(x)·g(x)u ] ≥ -α(h(x))
```

If a controller selects, at every instant, a `u` satisfying this inequality, the classical result
(Ames et al., "Control Barrier Function Based Quadratic Programs for Safety Critical Systems",
IEEE TAC 2017 — the standard citation for this theorem) guarantees **forward invariance** of `C`:
`x(0) ∈ C ⟹ x(t) ∈ C ∀t ≥ 0`. This is the actual, provable statement behind "the system cannot
leave the safe set" — and it is a statement about `ḣ`, the *rate of change* of `h` under the
chosen control, not just about `h`'s value at any single instant.

## 2. `evaluate_trajectory()` — what it actually proves

`evaluate_trajectory(trajectory_points)` checks `h_i(x) ≥ 0` for all 11 constraints at each of `N`
discrete points along a planned route (`aerofleet/city/trajectory_builder.py` supplies these
points). This is real, useful, and exactly what it says: **verification that the planned route is
in the safe set at every sampled point.**

**What this does *not* prove**: that the drone stays in `C` *between* two consecutive sampled
points. `h` is only evaluated at the samples; nothing here bounds how `h` could behave in the gap.
A rigorous version of this claim needs one additional, checkable condition:

> If `h` is `L`-Lipschitz along the path (a real, computable bound — battery drain and horizontal
> distance both admit one) and consecutive waypoints are within `Δ ≤ h_min / L` of each other
> (where `h_min` is the smallest margin observed at either endpoint), then `h(x) ≥ 0` between the
> samples too.

**Real, current gap**: `trajectory_builder.py` does not currently enforce a maximum spacing between
waypoints — waypoint density comes from the underlying road graph's own node spacing, which is not
derived from any Lipschitz bound on `h`. This is a concrete, fixable gap, not a fundamental one: the
fix is a `Δ`-bound check added to `trajectory_builder.py`, using the same edge-length data it
already has, and it should be done *before* this section can honestly claim more than "verified at
discrete samples." Framed as required follow-up work in the paper's methods section, not glossed
over — this is exactly the kind of caveat this project's own code comments already model well
elsewhere (see e.g. `restricted_sites.py`'s "not a scrape of the live Digital Sky platform" note).

## 3. `run_asif_qp()` — what it actually is, precisely

The function's own docstring calls it an "ASIF Quadratic Program" solving
`u_act = argmin ‖u_des − u‖² subject to h_i(x, u) ≥ 0`. Reading the real implementation
(`cbf_gate.py` lines 218-253), the constraint actually enforced per near-active `h_i` is:

```
h_i(x_current) + 0.01·‖u‖² ≥ 0
```

**This is not yet the textbook CBF-QP constraint.** The classical form constrains `ḣ`, i.e. how `u`
*changes* `h` going forward (`∇h(x)·g(x)u ≥ -α(h(x)) - ∇h(x)·f(x)`), which requires a system
dynamics model `f(x), g(x)` relating control input to state evolution. The current implementation
has no such dynamics model — `h_i` is evaluated once at the *current*, static state, independent of
`u`, and `u` only enters through the quadratic penalty term. This makes the current solver a
**control-effort-regularized feasibility filter around a static margin**, not a CBF-QP in the sense
the forward-invariance theorem in §1 applies to.

**What *can* honestly be claimed about it as-is**:
- The optimization is well-posed: `‖u_des − u‖²` is convex, the feasible set (when non-empty) is
  convex (a quadratic inequality in `‖u‖` is convex for the relevant sign), so SLSQP's local
  solution is the global minimum when one exists.
- `was_modified` correctly reports whether the filter changed anything (verified by
  `tests/unit/test_cbf_gate.py`, if such coverage exists — confirm before citing).
- It never *removes* a real per-point `h_i ≥ 0` violation check — `evaluate_trajectory()` still
  independently verifies the resulting state, so this function cannot cause a false "safe" verdict
  to reach a decision; at worst it fails to find a correction and the gate rejects, which is the
  safe failure mode.

**What it does *not* yet let you claim**: a Lyapunov-style or Nagumo forward-invariance guarantee.
That requires adding the real `f(x,u)` term.

## 4. The concrete path to a fully rigorous claim (recommended, not yet done)

If the paper's central safety claim should rest on the classical theorem rather than "verified at
discrete points, with a documented sampling-density gap":

1. Add an explicit, even simple, drone dynamics model (`ẋ = v`, `v̇ = u/m − drag(v)` is already
   close to what `unity/AeroFleetValidation/Assets/Editor/RouteValidator.cs`'s physics validator
   implements — the same model could be reused here as `f(x,u)`, closing the loop between the two
   pieces of this project rather than maintaining the dynamics assumption in two places).
2. Rewrite `run_asif_qp`'s constraint as the real `ḣ ≥ -α(h)` form using that model.
3. Add the `Δ`-spacing bound from §2 to `trajectory_builder.py`.
4. With both in place, the paper can cite Ames et al. (2017) directly and claim genuine forward
   invariance — not before.

## 5. What to write in the paper today, honestly

Given the above, the defensible claim right now is:

> "The system verifies, via 11 named constraint functions evaluated at every planned waypoint, that
> a dispatched route satisfies all safety margins at each sampled point (§2), and includes a
> quadratic-program-based minimally-invasive correction filter for near-violations at the current
> state (§3). A full continuous-time forward-invariance guarantee in the sense of Ames et al. (2017)
> requires two additions — a waypoint-spacing bound derived from a Lipschitz constant on each
> constraint, and an explicit dynamics model in the correction filter — both identified precisely
> and left as near-term future work (§4), rather than asserted as already proven."

This is a weaker-sounding claim than "formally verified safe," and it is the honest one. A Q1
reviewer who knows CBF theory will respect precision about what's proven over an inflated claim
that doesn't survive a close read of the code.
