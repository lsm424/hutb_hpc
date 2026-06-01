import os
import sys
import subprocess
import time


def run_experiment(name, script):
    print(f"\n{'='*70}")
    print(f"Running: {name}")
    print(f"{'='*70}")
    start = time.time()

    result = subprocess.run(
        [sys.executable, script],
        capture_output=False,
        text=True,
        cwd=os.path.dirname(os.path.abspath(__file__)),
    )

    elapsed = time.time() - start
    print(f"\nCompleted in {elapsed:.1f}s (exit code: {result.returncode})")
    return result.returncode == 0


def main():
    experiments = [
        ("Experiment 1: Cross-Metric Adaptation", "experiment1_cross_metric.py"),
        ("Experiment 2: Transition Response", "experiment2_transition.py"),
        ("Experiment 3: Bucket Density Boundary", "experiment3_bucket_density.py"),
        ("Experiment 4: Anti-Spike Robustness", "experiment4_anti_spike.py"),
        ("Experiment 5: End-to-End Performance", "experiment5_performance.py"),
    ]

    os.makedirs("plots", exist_ok=True)

    results = []
    for name, script in experiments:
        success = run_experiment(name, script)
        results.append((name, success))

    print(f"\n{'='*70}")
    print("ALL EXPERIMENTS COMPLETED")
    print(f"{'='*70}")
    for name, success in results:
        status = "PASS" if success else "FAIL"
        print(f"  [{status}] {name}")

    print(f"\nPlots saved to: {os.path.abspath('plots')}")


if __name__ == "__main__":
    main()
