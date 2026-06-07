#!/usr/bin/env python3
"""
Generate speedup and efficiency plots from benchmark results.
Requires: matplotlib, numpy, json
"""

import json
from pathlib import Path
import sys

if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def generate_plots():
    """Load benchmark results and generate matplotlib plots."""
    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("ERROR: matplotlib and numpy are required for plotting.")
        print("Install with: pip install matplotlib numpy")
        return
    
    # Load results
    results_file = Path("benchmark_results.json")
    if not results_file.exists():
        print(f"ERROR: {results_file} not found. Run benchmark.py first.")
        return
    
    with open(results_file) as f:
        results = json.load(f)
    
    if not results:
        print("No results to plot.")
        return
    
    # Create figure with subplots
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    fig.suptitle("Langton's Ant MPI Performance Analysis", fontsize=16, fontweight='bold')
    
    # 1. Strong Scaling - Speedup
    if "strong" in results:
        ax = axes[0, 0]
        strong = results["strong"]
        p_values = sorted(strong.keys(), key=int)
        speedups = [strong[str(p)].get("speedup", 1.0) for p in p_values]
        
        ax.plot(p_values, speedups, 'bo-', linewidth=2, markersize=8, label="Actual")
        # Ideal line
        ideal = p_values
        ax.plot(p_values, ideal, 'r--', linewidth=2, label="Ideal (S=P)")
        
        ax.set_xlabel("Number of Processes (P)")
        ax.set_ylabel("Speedup S(P)")
        ax.set_title("Strong Scaling (N=500×500)")
        ax.grid(True, alpha=0.3)
        ax.legend()
        ax.set_xticks(p_values)
    
    # 2. Strong Scaling - Efficiency
    if "strong" in results:
        ax = axes[0, 1]
        strong = results["strong"]
        p_values = sorted(strong.keys(), key=int)
        efficiencies = [strong[str(p)].get("efficiency", 0) for p in p_values]
        
        ax.bar(range(len(p_values)), efficiencies, color='green', alpha=0.7)
        ax.axhline(y=80, color='orange', linestyle='--', label="80% threshold")
        ax.set_xlabel("Number of Processes (P)")
        ax.set_ylabel("Efficiency E(P) [%]")
        ax.set_title("Parallel Efficiency")
        ax.set_xticks(range(len(p_values)))
        ax.set_xticklabels(p_values)
        ax.set_ylim([0, 105])
        ax.grid(True, alpha=0.3, axis='y')
        ax.legend()
    
    # 3. Weak Scaling - Execution Time
    if "weak" in results:
        ax = axes[1, 0]
        weak = results["weak"]
        p_values = sorted(weak.keys(), key=int)
        times = [weak[str(p)].get("time", 0) for p in p_values]
        
        ax.plot(p_values, times, 'g^-', linewidth=2, markersize=8)
        # Ideal would be constant
        if times:
            avg_time = sum(times) / len(times)
            ax.axhline(y=avg_time, color='red', linestyle='--', label="Ideal (constant)")
        
        ax.set_xlabel("Number of Processes (P)")
        ax.set_ylabel("Execution Time [s]")
        ax.set_title("Weak Scaling (N/P = const)")
        ax.grid(True, alpha=0.3)
        ax.legend()
        ax.set_xticks(p_values)
    
    # 4. Weak Scaling - Efficiency
    if "weak" in results:
        ax = axes[1, 1]
        weak = results["weak"]
        p_values = sorted(weak.keys(), key=int)
        efficiencies = [weak[str(p)].get("efficiency", 0) for p in p_values]
        
        ax.bar(range(len(p_values)), efficiencies, color='purple', alpha=0.7)
        ax.axhline(y=80, color='orange', linestyle='--', label="80% threshold")
        ax.set_xlabel("Number of Processes (P)")
        ax.set_ylabel("Efficiency E(P) [%]")
        ax.set_title("Weak Scaling Efficiency")
        ax.set_xticks(range(len(p_values)))
        ax.set_xticklabels(p_values)
        ax.set_ylim([0, 105])
        ax.grid(True, alpha=0.3, axis='y')
        ax.legend()
    
    # Save figure
    output_file = "benchmark_plots.png"
    plt.tight_layout()
    plt.savefig(output_file, dpi=150)
    print(f"✓ Plots saved to: {output_file}")
    # plt.show()

if __name__ == "__main__":
    generate_plots()
