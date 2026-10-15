
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit_ibm_runtime.fake_provider import FakeManilaV2

qc = QuantumCircuit(4, 4)
qc.h(range(4))
qc.measure(range(4), range(4))

ideal = AerSimulator()
noisy = AerSimulator.from_backend(FakeManilaV2())

# Try ideal first, then noisy
backend = noisy

compiled = transpile(qc, backend)
result = backend.run(compiled, shots=1024).result()

print(result.get_counts())
