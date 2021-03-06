import numpy as np
import cupy as cp
import h5py
from include.phaseImprinting import get_phase
import include.symplecticMethod as sm

"""Creates a HQV dipole in one of the components of the system and evolves the dynamics in real time."""

# --------------------------------------------------------------------------------------------------------------------
# Controlled variables:
# --------------------------------------------------------------------------------------------------------------------
Nx, Ny = 128, 128
Mx, My = Nx // 2, Ny // 2  # Number of grid pts
dx = dy = 1  # Grid spacing
dkx = np.pi / (Mx * dx)
dky = np.pi / (My * dy)  # K-space spacing
len_x = Nx * dx  # Box length
len_y = Ny * dy
x = cp.arange(-Mx, Mx) * dx
y = cp.arange(-My, My) * dy
X, Y = cp.meshgrid(x, y)  # Spatial meshgrid

# k-space arrays and meshgrid:
kx = cp.arange(-Mx, Mx) * dkx
ky = cp.arange(-My, My) * dky
Kx, Ky = cp.meshgrid(kx, ky)  # K-space meshgrid
Kx, Ky = cp.fft.fftshift(Kx), cp.fft.fftshift(Ky)

# Potential and interaction parameters
V = 0.  # Doubly periodic box
g1 = 4
g2 = 4
g12 = 3
mu_1 = 1
mu_2 = 1

# Time steps, number and wavefunction save variables
Nt = 150000
Nframe = 300   # Save data every Nframe number of timesteps
dt = 1e-2  # Imaginary time timestep
t = 0.
save_index = 0   # Array index

# --------------------------------------------------------------------------------------------------------------------
# Generate the initial state:
# --------------------------------------------------------------------------------------------------------------------
# Initial state parameters:
n0 = cp.ones(shape=(Nx, Ny))  # Background density

# Generate phase:
N_vort = 2  # One dipole
positions = [-2.5, -32, 2.5, -32]
theta = get_phase(N_vort, positions, Nx, Ny, cp.asnumpy(X), cp.asnumpy(Y), len_x, len_y)

# Generate initial wavefunctions:
psi_1 = cp.sqrt(n0 / 2) * cp.exp(1j * cp.asarray(theta))
psi_2 = cp.sqrt(n0 / 2)
psi_1_k = cp.fft.fft2(psi_1)
psi_2_k = cp.fft.fft2(psi_2)

# Getting atom number for renormalisation in imaginary time evolution
atom_num_1 = dx * dy * cp.sum(cp.abs(psi_1) ** 2)
atom_num_2 = dx * dy * cp.sum(cp.abs(psi_2) ** 2)

# Phase of initial state to allow fixing of phase during imaginary time evolution
theta_fix_1 = np.angle(psi_1)
theta_fix_2 = np.angle(psi_2)

# ------------------------------------------------------------------------------------------------------------------
# Imaginary time evolution
# ------------------------------------------------------------------------------------------------------------------
for i in range(2000):
    # Kinetic step:
    sm.kinetic_evolution(psi_1_k, -1j * dt, Kx, Ky)
    sm.kinetic_evolution(psi_2_k, -1j * dt, Kx, Ky)

    psi_1 = cp.fft.ifft2(psi_1_k)
    psi_2 = cp.fft.ifft2(psi_2_k)

    # Potential step:
    psi_1, psi_2 = sm.potential_evolution(psi_1, psi_2, -1j * dt, g1, g2, g12, mu_1, mu_2)

    psi_1_k = cp.fft.fft2(psi_1)
    psi_2_k = cp.fft.fft2(psi_2)

    # Kinetic step:
    sm.kinetic_evolution(psi_1_k, -1j * dt, Kx, Ky)
    sm.kinetic_evolution(psi_2_k, -1j * dt, Kx, Ky)

    # Re-normalising:
    atom_num_new_1 = dx * dy * cp.sum(cp.abs(cp.fft.ifft2(psi_1_k)) ** 2)
    atom_num_new_2 = dx * dy * cp.sum(cp.abs(cp.fft.ifft2(psi_2_k)) ** 2)
    psi_1_k = cp.fft.fft2(cp.sqrt(atom_num_1) * cp.fft.ifft2(psi_1_k) / cp.sqrt(atom_num_new_1))
    psi_2_k = cp.fft.fft2(cp.sqrt(atom_num_2) * cp.fft.ifft2(psi_2_k) / cp.sqrt(atom_num_new_2))

    # Fixing phase:
    psi_1 = cp.fft.ifft2(psi_1_k)
    psi_2 = cp.fft.ifft2(psi_2_k)
    psi_1 *= cp.exp(1j * theta_fix_1) / cp.exp(1j * cp.angle(psi_1))
    psi_2 *= cp.exp(1j * theta_fix_2) / cp.exp(1j * cp.angle(psi_2))
    psi_1_k = cp.fft.fft2(psi_1)
    psi_2_k = cp.fft.fft2(psi_2)

# ------------------------------------------------------------------------------------------------------------------
# Creating save file and saving initial data
# ------------------------------------------------------------------------------------------------------------------
filename = 'HQV_dipole'    # Name of file to save data to
data_path = 'data/{}.hdf5'.format(filename)

with h5py.File(data_path, 'w') as data:
    # Saving spatial data:
    data.create_dataset('grid/x', x.shape, data=cp.asnumpy(x))
    data.create_dataset('grid/y', y.shape, data=cp.asnumpy(y))

    # Saving time variables:
    data.create_dataset('time/Nt', data=Nt)
    data.create_dataset('time/dt', data=dt)
    data.create_dataset('time/Nframe', data=Nframe)

    # Creating empty wavefunction datasets to store data:
    data.create_dataset('wavefunction/psi_1', (Nx, Ny, 1), maxshape=(Nx, Ny, None), dtype='complex64')
    data.create_dataset('wavefunction/psi_2', (Nx, Ny, 1), maxshape=(Nx, Ny, None), dtype='complex64')

    # Stores initial state:
    data.create_dataset('initial_state/psi_1', data=cp.asnumpy(cp.fft.ifft2(psi_1_k)))
    data.create_dataset('initial_state/psi_2', data=cp.asnumpy(cp.fft.ifft2(psi_2_k)))

# ------------------------------------------------------------------------------------------------------------------
# Real time evolution
# ------------------------------------------------------------------------------------------------------------------
for i in range(Nt):
    # Kinetic step:
    sm.kinetic_evolution(psi_1_k, dt, Kx, Ky)
    sm.kinetic_evolution(psi_2_k, dt, Kx, Ky)

    psi_1 = cp.fft.ifft2(psi_1_k)
    psi_2 = cp.fft.ifft2(psi_2_k)

    # Potential step:
    psi_1, psi_2 = sm.potential_evolution(psi_1, psi_2, dt, g1, g2, g12, mu_1, mu_2)

    psi_1_k = cp.fft.fft2(psi_1)
    psi_2_k = cp.fft.fft2(psi_2)

    # Kinetic step:
    sm.kinetic_evolution(psi_1_k, dt, Kx, Ky)
    sm.kinetic_evolution(psi_2_k, dt, Kx, Ky)

    # Saves data
    if np.mod(i + 1, Nframe) == 0:
        with h5py.File(data_path, 'r+') as data:
            new_psi_1 = data['wavefunction/psi_1']
            new_psi_2 = data['wavefunction/psi_2']
            new_psi_1.resize((Nx, Ny, save_index + 1))
            new_psi_2.resize((Nx, Ny, save_index + 1))
            new_psi_1[:, :, save_index] = cp.asnumpy(cp.fft.ifft2(psi_1_k))
            new_psi_2[:, :, save_index] = cp.asnumpy(cp.fft.ifft2(psi_2_k))
        save_index += 1

    # Prints current time
    if np.mod(i, Nframe) == 0:
        print('t = %1.4f' % t)

    t += dt
