import csv
import os
import matplotlib.pyplot as plt

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
csv_path = os.path.join(root, "results", "iperf3_confirmed_trials.csv")
out_dir = os.path.join(root, "results", "graphs")
os.makedirs(out_dir, exist_ok=True)

with open(csv_path, newline="") as f:
    rows = list(csv.DictReader(f))

labels = [
    f"Trial {r['trial']} ({r['duration_seconds']} s)"
    for r in rows
]
values = [float(r["receiver_mbps"]) for r in rows]

plt.figure(figsize=(8, 5))
bars = plt.bar(labels, values)
plt.title("P4 VXLAN: TCP Receiver Throughput")
plt.ylabel("Receiver throughput (Mbps)")
plt.xlabel("iperf3 trial")
plt.ylim(0, max(values) * 1.2)

for bar, value in zip(bars, values):
    plt.text(bar.get_x() + bar.get_width() / 2,
             bar.get_height(),
             f"{value:.1f}",
             ha="center", va="bottom")

plt.tight_layout()
path = os.path.join(out_dir, "iperf3_receiver_throughput.png")
plt.savefig(path, dpi=200)
plt.close()
print(f"Saved graph: {path}")
print(f"Mean of the two 10-second trials: "
      f"{sum(values[1:]) / len(values[1:]):.2f} Mbps")
