# -*- coding: utf-8 -*-

"""
raman.raman
===============
This module contains the class RamanSolver to solve the set of Raman ODE equations.

@Author: Alessio Ferrari
"""

import numpy as np
import raman.utilities as ut
from scipy.integrate import solve_bvp
from scipy.integrate import cumtrapz
from scipy.interpolate import interp1d
import scipy.constants as ph
import matplotlib.pyplot as plt
from matplotlib import cm

class RamanSolver:

    def __init__(self, fiber_information=None):
        """ Initialize the fiber object with its physical parameters

        :param length: fiber length in m.
        :param alphap: fiber power attenuation coefficient vs frequency in 1/m. numpy array
        :param freq_alpha: frequency axis of alphap in Hz. numpy array
        :param cr_raman: Raman efficiency vs frequency offset in 1/W/m. numpy array
        :param freq_cr: reference frequency offset axis for cr_raman. numpy array
        :param solver_params: namedtuple containing the solver parameters (optional).
        """
        self._fiber_information = fiber_information
        self._solver_params = None
        self._spectral_information = None
        self._raman_pump_information = None
        self._raman_bvp_solution = None
        self._raman_ase_solution = None

    @property
    def fiber_information(self):
        return self._fiber_information

    @fiber_information.setter
    def fiber_information(self, fiber_information):
        self._fiber_information = fiber_information
        self._raman_bvp_solution = None

    @property
    def spectral_information(self):
        return self._spectral_information

    @spectral_information.setter
    def spectral_information(self, spectral_information):
        """

        :param spectral_information: namedtuple containing all the spectral information about carriers and eventual Raman pumps
        :return:
        """
        self._spectral_information = spectral_information
        self._raman_bvp_solution = None

    @property
    def raman_pump_information(self):
        return self._raman_pump_information

    @raman_pump_information.setter
    def raman_pump_information(self, raman_pump_information):
        self._raman_pump_information = raman_pump_information

    @property
    def solver_params(self):
        return self._solver_params

    @solver_params.setter
    def solver_params(self, solver_params):
        """
        :param solver_params: namedtuple containing the solver parameters (optional).
        :return:
        """
        self._solver_params = solver_params
        self._raman_bvp_solution = None

    @property
    def raman_ase_solution(self):
        if self._raman_ase_solution is None:

            # SET STUFF
            fiber_length = self.fiber_information.length
            attenuation_coefficient = self.fiber_information.attenuation_coefficient
            raman_coefficient = self.fiber_information.raman_coefficient

            spectral_info = self.spectral_information
            raman_pump_information = self.raman_pump_information

            z_resolution = self.solver_params.z_resolution
            tolerance = self.solver_params.tolerance
            verbose = self.solver_params.verbose

            if verbose:
                print('Start computing fiber Raman ASE')

            power_spectrum, freq_array, prop_direct = ut.compute_power_spectrum(spectral_info, raman_pump_information)

            if len(attenuation_coefficient.alpha_power) >= 2:
                interp_alphap = interp1d(attenuation_coefficient.frequency, attenuation_coefficient.alpha_power)
                alphap_fiber = interp_alphap(freq_array)
            else:
                alphap_fiber = attenuation_coefficient.alpha_power * np.ones(freq_array.shape)

            freq_diff = abs(freq_array - np.reshape(freq_array, (len(freq_array), 1)))
            if len(raman_coefficient.cr) >= 2:
                interp_cr = interp1d(raman_coefficient.frequency, raman_coefficient.cr)
                cr = interp_cr(freq_diff)
            else:
                cr = raman_coefficient.cr * np.ones(freq_diff.shape)

            # z propagation axis
            z_array = self.raman_bvp_solution.z
            pase0 = np.zeros(freq_array.shape)

            power_aselin = self._ase_int(z_array, self.raman_bvp_solution.power, alphap_fiber, freq_array, cr, freq_diff, pase0)
            power_ase = 10 * np.log10(power_aselin) + 30
            X, Y = np.meshgrid(z_array * 1e-3, freq_array * 1e-12)

            fig4 = plt.figure()
            ax = fig4.gca(projection='3d')
            surf = ax.plot_surface(X, Y, power_ase, rstride=1, cstride=1, cmap=cm.coolwarm,
                                   linewidth=0, antialiased=False)
            ax.set_xlabel('z [km]')
            ax.set_ylabel('f [THz]')
            ax.set_zlabel('power ase [dBm]')

            fig4.colorbar(surf, shrink=0.5, aspect=5)

            fig4 = plt.figure()
            plt.plot(z_array * 1e-3, power_ase.transpose())
            plt.xlabel('z [km]')
            plt.ylabel('Power ase [dBm]')
            plt.grid()

            plt.show()
            print(1)
            # self._raman_ase_solution = raman_ase_solution

        return self._raman_ase_solution

    def _ase_int(self, z_array, raman_matrix, alphap_fiber, freq_array, cr_raman_matrix, freq_diff, pase0):
        dx = self.solver_params.z_resolution
        h = ph.value('Planck constant')
        Kb = ph.value('Boltzmann constant')
        Bn = 32e9
        T = 298

        ase = np.nan * np.ones(raman_matrix.shape)
        int_pump = cumtrapz(raman_matrix, z_array, dx=dx, axis=1, initial=0)

        for f_ind, f_ase in enumerate(freq_array):
            cr_raman = cr_raman_matrix[f_ind, :]
            vibrational_loss = f_ase / freq_array[:f_ind]
            eta = 1/(np.exp((h*freq_diff[f_ind, :])/(Kb*T)) - 1)

            int_alpha = -alphap_fiber[f_ind] * z_array
            int_rlossv = np.sum((cr_raman[:f_ind] * vibrational_loss * int_pump[:f_ind, :].transpose()).transpose(), axis=0)
            int_rgainv = np.sum((cr_raman[f_ind + 1:] * int_pump[f_ind + 1:, :].transpose()).transpose(), axis=0)

            int_A = int_alpha + int_rgainv + int_rlossv

            B = np.sum((cr_raman[f_ind+1:]*(1+eta[f_ind+1:])*raman_matrix[f_ind+1:, :].transpose()).transpose() * h*f_ase*Bn, axis=0)

            F = pase0[f_ind] * np.exp(int_A)
            C = np.exp(int_A) * cumtrapz(B*np.exp(-int_A), z_array, dx=dx, initial=0)

            ase[f_ind, :] = F + C

        return ase


    @property
    def raman_bvp_solution(self):
        """ Return rho fiber gain/loss profile induced by stimulated Raman scattering.

        :return: self._raman_bvp_solution: the fiber's electric field gain/loss profile vs frequency and z.
        scipy.interpolate.PPoly instance
        """

        if self._raman_bvp_solution is None:
            fiber_length = self.fiber_information.length
            attenuation_coefficient = self.fiber_information.attenuation_coefficient
            raman_coefficient = self.fiber_information.raman_coefficient

            spectral_info = self.spectral_information
            raman_pump_information = self.raman_pump_information

            z_resolution = self.solver_params.z_resolution
            tolerance = self.solver_params.tolerance
            verbose = self.solver_params.verbose

            if verbose:
                print('Start computing fiber Raman profile')

            power_spectrum, freq_array, prop_direct = ut.compute_power_spectrum(spectral_info, raman_pump_information)

            if len(attenuation_coefficient.alpha_power) >= 2:
                interp_alphap = interp1d(attenuation_coefficient.frequency, attenuation_coefficient.alpha_power)
                alphap_fiber = interp_alphap(freq_array)
            else:
                alphap_fiber = attenuation_coefficient.alpha_power * np.ones(freq_array.shape)

            freq_diff = abs(freq_array - np.reshape(freq_array, (len(freq_array), 1)))
            if len(raman_coefficient.cr) >= 2:
                interp_cr = interp1d(raman_coefficient.frequency, raman_coefficient.cr)
                cr = interp_cr(freq_diff)
            else:
                cr = raman_coefficient.cr * np.ones(freq_diff.shape)

            # z propagation axis
            z = np.arange(0, fiber_length+1, z_resolution)

            ode_function = lambda z, p: self._ode_raman(z, p, alphap_fiber, freq_array, cr, prop_direct)
            boundary_residual = lambda ya, yb: self._residuals_raman(ya, yb, power_spectrum, prop_direct)
            initial_guess_conditions = self._initial_guess_raman(z, power_spectrum, alphap_fiber, prop_direct)

            # ODE SOLVER
            raman_bvp_solution = solve_bvp(ode_function, boundary_residual, z, initial_guess_conditions, tol=tolerance, verbose=verbose)

            rho = (raman_bvp_solution.y.transpose() / power_spectrum).transpose()
            rho = np.sqrt(rho)    # From power attenuation to field attenuation

            setattr(raman_bvp_solution, 'frequency', freq_array)
            setattr(raman_bvp_solution, 'z', raman_bvp_solution.x)
            setattr(raman_bvp_solution, 'rho', rho)
            setattr(raman_bvp_solution, 'power', raman_bvp_solution.y)
            delattr(raman_bvp_solution, 'x')
            delattr(raman_bvp_solution, 'y')

            self._raman_bvp_solution = raman_bvp_solution

        return self._raman_bvp_solution

    def _residuals_raman(self, ya, yb, power_spectrum, prop_direct):

        computed_boundary_value = np.zeros(ya.size)

        for index, direction in enumerate(prop_direct):
            if direction == +1:
                computed_boundary_value[index] = ya[index]
            else:
                computed_boundary_value[index] = yb[index]

        return power_spectrum - computed_boundary_value

    def _initial_guess_raman(self, z, power_spectrum, alphap_fiber, prop_direct):
        """ Computes the initial guess knowing the boundary conditions

        :param z: patial axis [m]. numpy array
        :param power_spectrum: power in each frequency slice [W].    Frequency axis is defined by freq_array. numpy array
        :param alphap_fiber: frequency dependent fiber attenuation of signal power [1/m]. Frequency defined by freq_array. numpy array
        :param prop_direct: indicates the propagation direction of each power slice in power_spectrum:
        +1 for forward propagation and -1 for backward propagation. Frequency defined by freq_array. numpy array
        :return: power_guess: guess on the initial conditions [W]. The first ndarray index identifies the frequency slice,
        the second ndarray index identifies the step in z. ndarray
        """

        power_guess = np.empty((power_spectrum.size, z.size))
        for f_index, power_slice in enumerate(power_spectrum):
            if prop_direct[f_index] == +1:
                power_guess[f_index, :] = np.exp(-alphap_fiber[f_index] * z) * power_slice
            else:
                power_guess[f_index, :] = np.exp(-alphap_fiber[f_index] * z[::-1]) * power_slice

        return power_guess


    def _ode_raman(self, z, power_spectrum, alphap_fiber, freq_array, cr_raman_matrix, prop_direct):
        """ Aim of ode_raman is to implement the set of ordinary differential equations (ODEs) describing the Raman effect.

        :param z: spatial axis (unused).
        :param power_spectrum: power in each frequency slice [W].    Frequency axis is defined by freq_array. numpy array. Size n
        :param alphap_fiber: frequency dependent fiber attenuation of signal power [1/m]. Frequency defined by freq_array. numpy array. Size n
        :param freq_array: reference frequency axis [Hz]. numpy array. Size n
        :param cr_raman: Cr(f) Raman gain efficiency variation in frequency [1/W/m]. Frequency defined by freq_array. numpy ndarray. Size nxn
        :param prop_direct: indicates the propagation direction of each power slice in power_spectrum:
        +1 for forward propagation and -1 for backward propagation. Frequency defined by freq_array. numpy array. Size n
        :return: dP/dz: the power variation in dz [W/m]. numpy array. Size n
        """

        dpdz = np.nan * np.ones(power_spectrum.shape)
        for f_ind, power in enumerate(power_spectrum):
            cr_raman = cr_raman_matrix[f_ind, :]
            vibrational_loss = freq_array[f_ind] / freq_array[:f_ind]

            for z_ind, power_sample in enumerate(power):
                raman_gain = np.sum(cr_raman[f_ind+1:] * power_spectrum[f_ind+1:, z_ind])
                raman_loss = np.sum(vibrational_loss * cr_raman[:f_ind] * power_spectrum[:f_ind, z_ind])

                dpdz_element = prop_direct[f_ind] * (-alphap_fiber[f_ind] + raman_gain - raman_loss) * power_sample
                dpdz[f_ind][z_ind] = dpdz_element

        return np.vstack(dpdz)
