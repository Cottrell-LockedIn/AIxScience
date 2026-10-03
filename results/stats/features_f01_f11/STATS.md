# Stats: features_f01_f11
config_hash: de199d6c8d69
git_sha: bf71ff6
reference_batch: Batch_3; source: Polaron clarification; config auto resolved
phase_identity: stated by Polaron, not image-verified
images: 31; features used: 11; zero-MAD columns dropped: none
robust z: median and 1.4826*MAD per feature across all images, without batch labels
Gaussian MMD bandwidth: 5.131 (median pairwise Euclidean distance over all robust-z images)
permutations: 1000 image-label draws per pair; seed=0; plus-one p; BH over 9 pair/metric tests
Batch_3 null: 1000 random 7/10 splits, size-matched to 7-image batches; smaller reference side gives wider/conservative bands than 7/17
null p95/p99: median_shift=0.9527/1.355; energy_distance=1.972/2.366; mmd2_unbiased=0.0746/0.1204
Batch_1 vs Batch_3: median_shift=0.5927, p=0.5924; energy_distance=1.539, p=0.2328; mmd2_unbiased=0.02108, p=0.2817
Batch_2 vs Batch_3: median_shift=0.6235, p=0.5275; energy_distance=1.131, p=0.3027; mmd2_unbiased=0.03164, p=0.1518
zero Batch_3-MAD columns excluded from median shift: none
consistency rank ascending (mean pairwise Euclidean): Batch_2=3.92 (rank 1, SE 0.3368, separable=true); Batch_3=5.476 (rank 2, SE 0.5955, separable=false); Batch_1=8.47 (rank 3, SE 1.541, separable=false)
