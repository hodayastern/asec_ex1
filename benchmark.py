import random
import time
import matplotlib.pyplot as plt

from client import Client
from server import Server


def benchmark_oram():
    db_sizes = [2**i for i in range(4, 12)]  # N = 16 to 2048
    trials = 100
    throughput_results = []
    latency_results = []

    for N in db_sizes:
        server = Server(N)
        client = Client(N)

        # Preload blocks
        for i in range(N):
            client.store_data(server, i, f"d{i%10:04}")

        # Benchmark
        start = time.time()
        for _ in range(trials):
            block_id = random.randint(0, N - 1)
            client.retrieve_data(server, block_id)
        end = time.time()

        total_time = end - start
        avg_latency = total_time / trials
        throughput = trials / total_time

        throughput_results.append((N, throughput))
        latency_results.append((throughput, avg_latency))

        print(f"N={N}, throughput={throughput:.2f} req/sec, latency={avg_latency:.6f} sec")

    # Plot
    Ns, throughputs = zip(*throughput_results)
    _, latencies = zip(*latency_results)

    plt.figure(figsize=(10, 4))
    plt.subplot(1, 2, 1)
    plt.plot(Ns, throughputs, marker='o')
    plt.xlabel('DB Size (N)')
    plt.ylabel('Throughput (requests/sec)')
    plt.title('Throughput vs. DB Size')

    plt.subplot(1, 2, 2)
    plt.plot(throughputs, latencies, marker='o')
    plt.xlabel('Throughput (requests/sec)')
    plt.ylabel('Latency (sec/request)')
    plt.title('Latency vs. Throughput')

    plt.tight_layout()
    plt.show()

benchmark_oram()
