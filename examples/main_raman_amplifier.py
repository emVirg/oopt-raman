import os
import datetime
import csv
import numpy as np
from collections import namedtuple
import raman.raman as rm
import raman.utilities as ut
from mpl_toolkits.mplot3d import axes3d
import matplotlib.pyplot as plt
from matplotlib import cm


def raman_gain_efficiency_from_csv(csv_file_name):
  with open(csv_file_name) as csv_file:
    cr_data = csv.reader(csv_file, delimiter=',')
    next(cr_data, None)
    cr = np.array([])
    frequency_cr = np.array([])
    for row in cr_data:
      frequency_cr = np.append(frequency_cr, float(row[0]))
      cr = np.append(cr, float(row[1]))

  return cr, frequency_cr


def main(fiber_information, spectral_information, raman_pump_information, raman_solver_infofrmation):

  fiber_under_test = rm.RamanSolver(fiber_information=fiber_information)
  fiber_under_test.spectral_information = spectral_information
  fiber_under_test.raman_pump_information = raman_pump_information
  fiber_under_test.solver_params = raman_solver_infofrmation

  raman_solution = fiber_under_test.raman_bvp_solution
  raman_ase = fiber_under_test.raman_ase_solution

  return raman_solution, raman_ase


if __name__ == '__main__':

  # FIBER PARAMETERS
  cr_file_name = './raman_gain_efficiency/SSMF.csv'
  cr, frequency_cr = raman_gain_efficiency_from_csv(cr_file_name)

  fiber_length = np.array([100e3])
  attenuation_coefficient_p = np.array([0.046e-3])
  frequency_attenuation = np.array([193.5e12])

  # WDM COMB PARAMETERS
  num_channels = 91
  delta_f = 50e9
  pch = 1e-3
  roll_off = 0.1
  symbol_rate = 32e9
  start_f = 191.0e12
  T = 298
  Bn = 32e9

  # RAMAN PUMP PARAMETERS
  pump_pow = [150e-3,   250e-3,   150e-3,   250e-3,   200e-3]
  pump_freq = [200.2670e12,  201.6129e12,  207.1823e12,  208.6231e12,  210.0840e12]
  prop_direction = [-1, -1, -1, -1, -1]
  num_pumps = len(pump_pow)

  # ODE SOLVER PARAMETERS
  z_resolution = 1e3
  tolerance = 1e-8
  verbose = 2

  # FIBER
  fiber_info = namedtuple('FiberInformation', 'length attenuation_coefficient raman_coefficient')
  attenuation_coefficient = namedtuple('AttenuationCoefficient', 'alpha_power frequency')
  raman_coefficient = namedtuple('RamanCoefficient', 'cr frequency')

  att_coeff = attenuation_coefficient(alpha_power=attenuation_coefficient_p, frequency=frequency_attenuation)
  raman_coeff = raman_coefficient(cr=cr, frequency=frequency_cr)
  fiber = fiber_info(length=fiber_length, attenuation_coefficient=att_coeff, raman_coefficient=raman_coeff)

  # SPECTRUM
  spectral_information = namedtuple('SpectralInformation', 'carriers')
  channel = namedtuple('Channel', 'channel_number frequency baud_rate roll_off power')
  power = namedtuple('Power', 'signal nonlinear_interference amplified_spontaneous_emission')

  carriers = tuple(channel(1 + ii, start_f + (delta_f * ii), symbol_rate, roll_off, power(pch, 0, 0))
                   for ii in range(0, num_channels))
  spectrum = spectral_information(carriers=carriers)

  # RAMAN PUMPS
  raman_pump_information = namedtuple('SpectralInformation', 'raman_pumps')
  pump = namedtuple('RamanPump', 'pump_number power frequency propagation_direction')
  pumps = tuple(pump(1 + ii, pump_pow[ii], pump_freq[ii], prop_direction[ii])
                for ii in range(0, num_pumps))
  raman_pumps = raman_pump_information(raman_pumps=pumps)

  # SOLVER PARAMETERS
  raman_solver_information = namedtuple('RamanSolverInformation', 'z_resolution tolerance verbose')
  solver_parameters = raman_solver_information(z_resolution=z_resolution, tolerance=tolerance, verbose=verbose)

  gain_loss_profile, raman_ase = main(fiber, spectrum, raman_pumps, solver_parameters)

  z_rho = gain_loss_profile.z
  freq_rho = gain_loss_profile.frequency
  rho = gain_loss_profile.rho
  power_slice = 10*np.log10(gain_loss_profile.power)+30

  z_ase = raman_ase.z[1:]
  freq_ase = raman_ase.frequency[0:-1]
  power_ase = 10*np.log10(raman_ase.power[:-1,1:])+30




  # PLOT RESULTS
  X, Y = np.meshgrid(z_rho*1e-3, freq_rho*1e-12)

  fig = plt.figure()
  ax = fig.gca(projection='3d')
  surf = ax.plot_surface(X, Y, 20 * np.log10(gain_loss_profile.rho), rstride=1, cstride=1, cmap=cm.coolwarm,
                         linewidth=0, antialiased=False)
  ax.set_xlabel('z [km]')
  ax.set_ylabel('f [THz]')
  ax.set_zlabel('rho [dB]')

  fig.colorbar(surf, shrink=0.5, aspect=5)

  fig2 = plt.figure()
  plt.plot(z_rho * 1e-3, (20 * np.log10(gain_loss_profile.rho.transpose())))
  plt.xlabel('z [km]')
  plt.ylabel('rho [dB]')
  plt.grid()

  fig = plt.figure()
  ax = fig.gca(projection='3d')
  surf = ax.plot_surface(X, Y, power_slice, rstride=1, cstride=1, cmap=cm.coolwarm,
                         linewidth=0, antialiased=False)
  ax.set_xlabel('z [km]')
  ax.set_ylabel('f [THz]')
  ax.set_zlabel('power [dBm]')

  fig.colorbar(surf, shrink=0.5, aspect=5)

  fig2 = plt.figure()
  plt.plot(z_rho * 1e-3, power_slice.transpose())
  plt.xlabel('z [km]')
  plt.ylabel('Power [dBm]')
  plt.grid()

  plt.show()



  # PLOT ASE
  X, Y = np.meshgrid(z_ase*1e-3, freq_ase*1e-12)

  fig4 = plt.figure()
  ax = fig4.gca(projection='3d')
  surf = ax.plot_surface(X, Y, power_ase, rstride=1, cstride=1, cmap=cm.coolwarm,
                         linewidth=0, antialiased=False)
  ax.set_xlabel('z [km]')
  ax.set_ylabel('f [THz]')
  ax.set_zlabel('power ase [dBm]')

  fig4.colorbar(surf, shrink=0.5, aspect=5)

  fig4 = plt.figure()
  plt.plot(z_ase * 1e-3, power_ase.transpose())
  plt.xlabel('z [km]')
  plt.ylabel('Power ase [dBm]')
  plt.grid()

  plt.show()

