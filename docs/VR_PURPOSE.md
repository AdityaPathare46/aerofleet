# What the VR view is for in AeroFleet 2.0, and how it is being tested

Replaces the justification in `docs/VR_RESEARCH_REFERENCES.md`, which was written for the earlier AI-dispatch
product (checking an AI council's story, watching a live delivery swarm). Neither exists in AeroFleet 2.0; that file is
kept only as a list of references and its sections 1, 5 and 6 no longer apply.

## The one job

**A flight debrief.** After a flight, a trainer or supervisor puts the reviewed flight on a 3D table and walks the pilot
through it: the plan, where the drone actually went, how high, and where each warning in the log happened. The pilots
in the use case are new (Namo Drone Didi pilots get 5 days of flying training), and after an incident the question
"whose fault was it?" is answered with facts on the table, not guesses.

It also rehearses the day's planned missions on one clock before they fly (*Rehearse in 3D* on Fleet Assurance).

What it is not: a live monitor (AeroFleet never connects to a drone in flight), a decision aid (no verdict comes from
it), or a claim that 3D is better.

## Why 3D could help, and why that is only a hypothesis

A route and a height are one shape in space. On a flat map the height is a separate chart, and the person has to join
the two in their head; on a table in a headset both are seen together, and walking round it adds depth. Published work
on depth in headsets says stereo and head movement help judge distances, and also that people underestimate distances
in VR (El Jamiy and Marsh 2019, in `VR_RESEARCH_REFERENCES.md` section 2). Those studies are not about flight logs, so
they motivate the question; they do not answer it.

## How it is tested: a declared study

`research/vr_study/PROTOCOL.md`, declared before the first participant. 12 students who are not on the team each judge
15 real flights on a 2D map with a height profile and 15 others on the 3D table in a Meta Quest 3, with the order and
flight sets counterbalanced. Each flight is real (public PX4 logs) with a known deviation injected (sideways 15 or 35 m,
upward 8 or 20 m) or none, so every answer is right or wrong against a key fixed in advance. Primary measure: share
answered right, headset against 2D (paired Wilcoxon, two-sided). The result is reported whatever it is.

If 3D is not better, the VR view stays a presentation and training aid, described as untested for accuracy, and the
report says so.

## What the study does not cover

* Real debriefs with real pilots and trainers (needs a partner operator).
* Mixed-reality passthrough, walking around the table standing, or long sessions.
* Whether a debrief changes how a pilot flies next time.
