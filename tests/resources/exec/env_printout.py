import os

print("--- environment dump start ---")
for name, value in sorted(os.environ.items()):
    print(f"{name}: {value}")
print("--- environment dump end---")
