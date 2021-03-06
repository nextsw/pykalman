import numpy as np
from scipy.interpolate import interp1d

E_0 = 2.5;         # initial energy in MeV
eslice = 0.05;     # slice energy in MeV


MS0 = 13.6;        # multiple scattering parameter (should be 13.6)
E_tol = 1e-3;      # energy tolerance value (energy is considered to be 0 if less than this value)

masse = 0.511;       # electron rest mass in MeV

# Gas configuration parameters.
Pgas = 10.;       # gas pressure in atm
Tgas = 293.15;    # gas temperature in Kelvin
LrXe = 1530.;     # xenon radiation length  * pressure in cm * bar
Lr = LrXe/(Pgas/1.01325);

# Physics constants.
pc_rho0 = 2.6867774e19;   # density of ideal gas at T=0C, P=1 atm in cm^(-3)
pc_m_Xe = 131.293;        # mass of xenon in amu
pc_NA = 6.02214179e23;    # Avogadro constant

# Read in the stopping power and interpolate.
xesp_tbl = np.loadtxt("xe_estopping_power_NIST.dat");
rho = pc_rho0*(Pgas/(Tgas/273.15))*(pc_m_Xe/pc_NA);
e_vals = xesp_tbl[:,0];
dEdx_vals = xesp_tbl[:,1];
e_vals = np.insert(e_vals,0,0.0);
dEdx_vals = np.insert(dEdx_vals,0,dEdx_vals[0]);
xesp = interp1d(e_vals,dEdx_vals*rho,kind='cubic');
