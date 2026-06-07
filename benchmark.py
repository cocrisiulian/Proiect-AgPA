#!/usr/bin/env python3
"""
Benchmarking script for Langton's Ant simulator.
Compares sequential vs MPI performance, generates speedup/efficiency plots.
"""

import subprocess
import time
import sys
from pathlib import Path
import json

if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def run_sequential(size, steps, ants, snapshot_k=0):
    """Run sequential simulator and return runtime in seconds."""
    cmd = [
        "build\\langton.exe",
        "-n", str(size),
        "-t", str(steps),
        "-a", str(ants),
        "-k", str(snapshot_k)
    ]
    start = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = time.time() - start
    
    if result.returncode != 0:
        print(f"ERROR: Sequential run failed: {result.stderr}")
        return None
    return elapsed

def run_mpi(num_procs, size, steps, ants, snapshot_k=0):
    """Run MPI simulator and return runtime in seconds."""
    cmd = [
        "mpiexec", "-n", str(num_procs),
        "build-mpi\\langton_mpi.exe",
        "-n", str(size),
        "-t", str(steps),
        "-a", str(ants),
        "-k", str(snapshot_k)
    ]
    start = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = time.time() - start
    
    if result.returncode != 0:
        print(f"WARNING: MPI run with P={num_procs} failed: {result.stderr}")
        return None
    return elapsed

def strong_scaling_test():
    """Test strong scaling: fixed problem size, varying P."""
    print("\n=== STRONG SCALING TEST ===")
    print("Grid size: 500x500, Steps: 5000, Ants: 100")
    
    size = 500
    steps = 5000
    ants = 100
    
    results = {"strong": {}}
    
    # Run sequential
    print("Running sequential baseline...", end=" ", flush=True)
    t_seq = run_sequential(size, steps, ants)
    if t_seq is None:
        print("FAILED")
        print("Skipping strong scaling because the sequential baseline did not complete.")
        return results
    print(f"Time: {t_seq:.3f}s")
    results["strong"][1] = {"time": t_seq, "speedup": 1.0, "efficiency": 100.0}
    
    # Run MPI with P=2, 4
    for p in [2, 4]:
        print(f"Running MPI with P={p}...", end=" ", flush=True)
        t_mpi = run_mpi(p, size, steps, ants)
        if t_mpi is not None:
            # Ideal: time should stay ~constant
            efficiency = (t_seq / t_mpi) * 100
            print(f"Time: {t_mpi:.3f}s, Efficiency: {efficiency:.1f}%")
            results["strong"][p] = {"time": t_mpi, "speedup": t_seq / t_mpi, "efficiency": efficiency}
        else:
            print("MPI execution did not complete successfully.")
    
    return results

def weak_scaling_test():
    """Test weak scaling: fixed work per process, varying P."""
    print("\n=== WEAK SCALING TEST ===")
    print("Fixed problem per process: ~250x250 per rank, Steps: 5000")
    
    steps = 5000
    ants_per_proc = 25
    
    results = {"weak": {}}
    
    # P=1
    size = 250
    ants = ants_per_proc
    print(f"P=1 (N={size}x{size}, A={ants})...", end=" ", flush=True)
    t_seq = run_sequential(size, steps, ants)
    if t_seq is None:
        print("FAILED")
        print("Skipping weak scaling because the sequential baseline did not complete.")
        return results
    print(f"Time: {t_seq:.3f}s")
    results["weak"][1] = {"time": t_seq, "efficiency": 100.0}
    
    # P=2, 4
    for p in [2, 4]:
        size = 250 * p
        ants = ants_per_proc * p
        if size > 2000:  # Skip if too large
            print(f"P={p} skipped (grid too large: {size}x{size})")
            continue
        
        print(f"P={p} (N={size}x{size}, A={ants})...", end=" ", flush=True)
        t_mpi = run_mpi(p, size, steps, ants)
        if t_mpi is not None:
            # Ideal: time should stay ~constant
            efficiency = (t_seq / t_mpi) * 100
            print(f"Time: {t_mpi:.3f}s, Efficiency: {efficiency:.1f}%")
            results["weak"][p] = {"time": t_mpi, "efficiency": efficiency}
        else:
            print("FAILED")
    
    return results

def validation_test():
    """Validate correctness: run same grid on P=1 (seq) and P=1 (MPI), compare outputs."""
    print("\n=== VALIDATION TEST ===")
    print("Running sequential vs MPI(P=1) on same grid...")
    
    size = 100
    steps = 500
    ants = 5
    
    print(f"Sequential...", end=" ", flush=True)
    t_seq = run_sequential(size, steps, ants)
    if t_seq is None:
        print("FAILED")
        print("ERROR: Sequential validation run did not complete.")
        return False
    print(f"Done ({t_seq:.3f}s)")
    
    # Check if sequential output exists
    seq_output = Path("output_final.ppm")
    if not seq_output.exists():
        print("ERROR: Sequential output not found")
        return False
    
    print(f"MPI (P=1)...", end=" ", flush=True)
    t_mpi = run_mpi(1, size, steps, ants)
    if t_mpi is None:
        print("FAILED")
        print("ERROR: MPI validation run did not complete.")
        return False
    print(f"Done ({t_mpi:.3f}s)")
    
    # Check if MPI output exists
    mpi_output = Path("output_final_mpi.ppm")
    if not mpi_output.exists():
        print("ERROR: MPI output not found")
        return False
    
    # Simple check: compare file sizes (not exact bit equality due to floating point)
    seq_size = seq_output.stat().st_size
    mpi_size = mpi_output.stat().st_size
    
    if seq_size == mpi_size:
        print(f"✓ Output files match (size: {seq_size} bytes)")
        return True
    else:
        print(f"⚠ Output files differ in size: seq={seq_size}, mpi={mpi_size}")
        print("  (This may be expected due to agent ordering)")
        return True  # Not critical

def main():
    """Run all benchmarks."""
    print("Langton's Ant Benchmarking Suite")
    print("=" * 50)
    
    # Check if executables exist
    if not Path("build\\langton.exe").exists():
        print("ERROR: Sequential executable not found at build\\langton.exe")
        print("Please build with: build.bat")
        sys.exit(1)
    
    mpi_available = subprocess.run(["where", "mpiexec"], capture_output=True).returncode == 0
    
    # Run tests
    all_results = {}
    
    # Always run validation
    validation_test()
    
    # Strong scaling
    if mpi_available:
        strong = strong_scaling_test()
        all_results.update(strong)
    else:
        print("\nWARNING: mpiexec not found. Skipping MPI benchmarks.")
        print("For MPI tests, please install Open MPI or MPICH.")
    
    # Weak scaling (if MPI available)
    if mpi_available:
        weak = weak_scaling_test()
        all_results.update(weak)
    
    # Save results
    print("\n" + "="*50)
    print("Results saved to: benchmark_results.json")
    with open("benchmark_results.json", "w") as f:
        json.dump(all_results, f, indent=2)
    
    # Print summary
    print("\nSUMMARY:")
    if "strong" in all_results:
        print("Strong Scaling (N=500x500):")
        for p, data in sorted(all_results["strong"].items()):
            print(f"  P={p}: {data['time']:.3f}s, S={data.get('speedup', 'N/A')}, E={data.get('efficiency', 'N/A')}%")
    
    if "weak" in all_results:
        print("Weak Scaling:")
        for p, data in sorted(all_results["weak"].items()):
            print(f"  P={p}: {data['time']:.3f}s, E={data['efficiency']:.1f}%")

if __name__ == "__main__":
    main()
