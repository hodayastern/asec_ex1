import time
import random
import matplotlib.pyplot as plt

from client import Client
from server import Server


def benchmark_oram(num_blocks, num_requests=30):
    client = Client(num_blocks)
    server = Server(num_blocks)

    # Initialize with data
    for i in range(num_blocks):
        client.store_data(server, i, f"{i:04d}")

    start_time = time.time()
    latencies = []

    for _ in range(num_requests):
        block_id = random.randint(0, num_blocks - 1)
        t0 = time.time()
        client.retrieve_data(server, block_id)
        t1 = time.time()
        latencies.append((t1 - t0) * 1000)  # in milliseconds

    end_time = time.time()
    total_time = end_time - start_time

    throughput = num_requests / total_time  # requests/sec
    avg_latency = sum(latencies) / len(latencies)

    return throughput, avg_latency


def run_benchmarks(num_requests=30):
    sizes = [32, 64, 128, 256, 512, 1024]
    results = []

    for N in sizes:
        print(f"Running benchmark for N = {N}...")
        throughput, latency = benchmark_oram(N, num_requests)
        print(f"N = {N}: Throughput = {throughput:.2f} req/sec, Avg Latency = {latency:.2f} ms")
        results.append((N, throughput, latency))

    return results


def plot_results(results):
    Ns = [r[0] for r in results]
    throughputs = [r[1] for r in results]
    latencies = [r[2] for r in results]

    plt.figure(figsize=(12, 5))

    # Plot 1: Throughput vs. DB size
    plt.subplot(1, 2, 1)
    plt.plot(Ns, throughputs, marker='o')
    plt.xscale('log', base=2)
    plt.xlabel("Database Size (N)")
    plt.ylabel("Throughput (requests/sec)")
    plt.title("Throughput vs. DB Size")
    plt.grid(True)

    # Plot 2: Latency vs. Throughput
    plt.subplot(1, 2, 2)
    
    sorted_pairs = sorted(zip(throughputs, latencies))
    throughputs_sorted, latencies_sorted = zip(*sorted_pairs)

    plt.plot(throughputs_sorted, latencies_sorted, marker='o')
    plt.xlabel("Throughput (requests/sec)")
    plt.ylabel("Average Latency (ms)")
    plt.title("Latency vs. Throughput")
    plt.grid(True)

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    results = run_benchmarks()
    plot_results(results)
