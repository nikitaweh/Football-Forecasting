Where we stand
The real finding from the sweep stands: the surrogate is the broken link — mean Pearson r = 0.018, sign-flips on 4 of 8 matchdays. The ensemble couldn't paper over that. Two honest paths from here:

Option A — drop the surrogate, rank on confidence proxies (MeanTopProb, MeanProbGap, MeanEntropy) only. Cheap, but those proxies measure self-certainty, not correctness — may not help much.
Retrain the surrogate with match-level features — currently it only sees (weights, H2H_K) → AvgNLL, blind to which matchday it's predicting. Feeding it match context (team strength gap, home/away, fixture difficulty) is the more principled fix, but a larger change.
My lean: A first as a quick diagnostic — if confidence-only ranking matches or beats the surrogate in a re-run, that itself tells us the surrogate was adding negative value. Then decide whether the heavier retrain is worth it. Want me to implement A?

My recommendation
Do Option A as cheap cleanup: rank on MeanProbGap (best calibrated) instead of the surrogate, and drop MeanEntropy (actively harmful). ~30 min, small guaranteed gain.
Then pivot to draw prediction — it's now clearly the highest-leverage open item, and it's the one thing that could move MD18/MD2 from losses to wins.
Want me to (1) implement Option A now, (2) jump straight to the draw work, or (3) do A then draws?