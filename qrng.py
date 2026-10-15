from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit_ibm_runtime.fake_provider import FakeManilaV2
from qiskit_aer.noise import amplitude_damping_error, NoiseModel, ReadoutError, depolarizing_error, phase_damping_error, thermal_relaxation_error

import numpy as np

NOISE_TYPES = ["depolarizing", "amplitude", "phase", "readout", "thermal",]

def build_random_noisy_circuit(rng, qubits):
    qc = QuantumCircuit(qubits, qubits)
    qc.h(range(qubits))
    noise_model = NoiseModel()
    applied_noise = []
    noise_count = int(rng.choice([1, 2, 5]))
    selected_types = rng.choice(NOISE_TYPES, size=noise_count, replace=False).tolist()

    print(f"Noise count: {noise_count}")
    print(f"Selected noise: {selected_types}")

    for q in range(qubits):
        for kind in selected_types:
            p = float(rng.uniform(0.01, 0.20))
            if kind == "depolarizing":
                error = depolarizing_error(p, 1)

            elif kind == "amplitude":
                error = amplitude_damping_error(p)

            elif kind == "phase":
                error = phase_damping_error(p)

            elif kind == "thermal":
                T1 = float(rng.uniform(30e-6, 80e-6))
                T2 = float(rng.uniform(0.5, 1.8) * T1)
                duration = float(rng.uniform(100e-9, 1000e-9))

                error = thermal_relaxation_error(
                    T1, T2, duration
                )

            elif kind == "readout":
                p01 = p
                p10 = p * 0.5

                error = ReadoutError([
                    [1 - p01, p01],
                    [p10, 1 - p10],
                ])

                noise_model.add_readout_error(error, [q])
                applied_noise.append((q, kind, p))
                continue

            qc.append(error.to_instruction(), [q])
            applied_noise.append((q, kind, p))

    qc.measure(range(qubits), range(qubits))
    return qc, noise_model, applied_noise, selected_types

def generate_quantum_number(qubits: int = 4, samples: int = 6):
    rng = np.random.default_rng()
    numbers = []

    for i in range(samples):
        qc, noise_model, applied, selected = (build_random_noisy_circuit(rng, qubits=qubits))
        sim = AerSimulator(method="density_matrix", noise_model=noise_model)
        compiled = transpile(qc, sim, optimization_level=0)
        result = sim.run(compiled, shots=1, memory=True).result()
        bits = result.get_memory()[0]
        value = int(bits, 2)
        numbers.append(value)
        print(f"Sample {i+1}: {value}")
        print(f"Noise applied: {selected}")

    print("Six numbers:", numbers)

    return numbers