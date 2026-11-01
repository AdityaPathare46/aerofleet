# Operator clustering (location proxy)

Declared in `research/px4_log_study/operator_cluster.py`.

```
{
 "declared_in": "research/px4_log_study/operator_cluster.py docstring",
 "n_sets": 60,
 "n_airframes": 134,
 "no_gps_fix": 20,
 "O1": {
  "clusters": 96,
  "size_hist": {
   "1": 84,
   "2": 6,
   "3": 4,
   "11": 1,
   "15": 1
  },
  "clusters_with_2plus_cases": 3,
  "sets_case_shares_cluster_with_control": 5
 },
 "O2": {
  "rbar": 0.6666666666666666,
  "mean": 0.6603962875728351,
  "ci": [
   0.5103094211822661,
   0.7898356625258799
  ],
  "p": 0.006,
  "case_clusters": 23,
  "control_clusters": 79,
  "holm": 0.042
 },
 "O3": {
  "sets": 55,
  "mean_rank": 0.6727272727272727,
  "p": 0.0034
 },
 "O4": {
  "sets": 23,
  "median_mean_rank": 0.6086956521739131,
  "median_p": 0.13685,
  "share_p_below_0025": 0.023
 },
 "O5": {
  "R0.5km": {
   "rbar": 0.6666666666666666,
   "mean": 0.6601152530005993,
   "ci": [
    0.5,
    0.7990441176470586
   ],
   "p": 0.01,
   "case_clusters": 24,
   "control_clusters": 80
  },
  "R10.0km": {
   "rbar": 0.6666666666666666,
   "mean": 0.6607686832108286,
   "ci": [
    0.4940361721611722,
    0.7937780448717948
   ],
   "p": 0.0035,
   "case_clusters": 21,
   "control_clusters": 75
  }
 },
 "wording": {
  "survives_operator_clustering": true,
  "overall": "supported"
 },
 "limits": "location is a proxy for operator; one operator may fly at several sites and several operators at one site; airframes without a GPS fix are their own cluster"
}
```
