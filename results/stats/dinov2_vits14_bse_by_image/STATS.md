# Stats: dinov2_vits14_bse_by_image
config_hash: de199d6c8d69
git_sha: bf71ff6
reference_batch: Batch_3; source: Polaron clarification; config auto resolved
phase_identity: stated by Polaron, not image-verified
images: 31; features used: 384; zero-MAD columns dropped: none
robust z: median and 1.4826*MAD per feature across all images, without batch labels
Gaussian MMD bandwidth: 28.06 (median pairwise Euclidean distance over all robust-z images)
permutations: 1000 image-label draws per pair; seed=0; plus-one p; BH over 9 pair/metric tests
Batch_3 null: 1000 random 7/10 splits, size-matched to 7-image batches; smaller reference side gives wider/conservative bands than 7/17
null p95/p99: median_shift=0.755/0.8319; energy_distance=8.829/10.2; mmd2_unbiased=0.05437/0.08527
Batch_1 vs Batch_3: median_shift=1.411, p=0.000999; energy_distance=14.66, p=0.001998; mmd2_unbiased=0.1541, p=0.001998
Batch_2 vs Batch_3: median_shift=0.8705, p=0.003996; energy_distance=8.777, p=0.01199; mmd2_unbiased=0.07657, p=0.01099
zero Batch_3-MAD columns excluded from median shift: none
consistency rank ascending (mean pairwise Euclidean): Batch_2=25.11 (rank 1, SE 2.416, separable=false); Batch_3=26.35 (rank 2, SE 0.8503, separable=true); Batch_1=36.04 (rank 3, SE 2.712, separable=false)
