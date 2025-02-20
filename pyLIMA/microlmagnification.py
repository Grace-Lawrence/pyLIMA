# -*- coding: utf-8 -*-
"""
Created on Tue Dec  8 14:37:33 2015

@author: ebachelet
"""

from __future__ import division
import numpy as np


import VBBinaryLensing

VBB = VBBinaryLensing.VBBinaryLensing()
VBB.Tol = 0.001
VBB.RelTol = 0.001


def impact_parameter(tau, uo):
    """
    The impact parameter U(t).
    "Gravitational microlensing by the galactic halo",Paczynski, B. 1986
    http://adsabs.harvard.edu/abs/1986ApJ...304....1P

    :param array_like tau: the tau define for example in
                               http://adsabs.harvard.edu/abs/2015ApJ...804...20C
    :param array_like uo: the uo define for example in
                              http://adsabs.harvard.edu/abs/2015ApJ...804...20C

    :return: the impact parameter U(t)
    :rtype: array_like
    """
    impact_param = (tau ** 2 + uo ** 2) ** 0.5  # u(t)

    return impact_param


def amplification_PSPL(tau, uo):
    """
    The Paczynski Point Source Point Lens magnification and the impact parameter U(t).
    "Gravitational microlensing by the galactic halo",Paczynski, B. 1986
    http://adsabs.harvard.edu/abs/1986ApJ...304....1P

    :param array_like tau: the tau define for example in
                           http://adsabs.harvard.edu/abs/2015ApJ...804...20C

    :param array_like uo: the uo define for example in
                         http://adsabs.harvard.edu/abs/2015ApJ...804...20C

    :return: the PSPL magnification A_PSPL(t) and the impact parameter U(t)
    :rtype: tuple, tuple of two array_like
    """
    # For notations, check for example : http://adsabs.harvard.edu/abs/2015ApJ...804...20C

    impact_param = impact_parameter(tau, uo)  # u(t)
    impact_param_square = impact_param ** 2  # u(t)^2

    amplification_pspl = (impact_param_square + 2) / (impact_param * (impact_param_square + 4) ** 0.5)

    # return both magnification and U, required by some methods
    return amplification_pspl


def Jacobian_amplification_PSPL(tau, uo):
    """ Same function as above, just also returns the impact parameter needed for the Jacobian PSPL model.
    The Paczynski Point Source Point Lens magnification and the impact parameter U(t).
    "Gravitational microlensing by the galactic halo",Paczynski, B. 1986
    http://adsabs.harvard.edu/abs/1986ApJ...304....1P

    :param array_like tau: the tau define for example in
                           http://adsabs.harvard.edu/abs/2015ApJ...804...20C

    :param array_like uo: the uo define for example in
                         http://adsabs.harvard.edu/abs/2015ApJ...804...20C

    :return: the PSPL magnification A_PSPL(t) and the impact parameter U(t)
    :rtype: tuple, tuple of two array_like
    """
    # For notations, check for example : http://adsabs.harvard.edu/abs/2015ApJ...804...20C

    impact_param = impact_parameter(tau, uo)  # u(t)
    impact_param_square = impact_param ** 2  # u(t)^2

    amplification_pspl = (impact_param_square + 2) / (impact_param * (impact_param_square + 4) ** 0.5)

    # return both magnification and U, required by some methods
    return amplification_pspl, impact_param


def amplification_FSPL(tau, uo, rho, gamma, yoo_table):
    """
    The Yoo et al. Finite Source Point Lens magnification.
    "OGLE-2003-BLG-262: Finite-Source Effects from a Point-Mass Lens",Yoo, J. et al 2004
    http://adsabs.harvard.edu/abs/2004ApJ...603..139Y

    :param array_like tau: the tau define for example in
                               http://adsabs.harvard.edu/abs/2015ApJ...804...20C

    :param array_like uo: the uo define for example in
                             http://adsabs.harvard.edu/abs/2015ApJ...804...20C

    :param float rho: the normalised angular source star radius

    :param float gamma: the microlensing limb darkening coefficient.

    :param array_like yoo_table: the Yoo et al. 2004 table approximation. See microlmodels for more details.

    :return: the FSPL magnification A_FSPL(t)
    :rtype: array_like
    """
    impact_param = impact_parameter(tau, uo)  # u(t)
    impact_param_square = impact_param ** 2  # u(t)^2

    amplification_pspl = (impact_param_square + 2) / (impact_param * (impact_param_square + 4) ** 0.5)

    z_yoo = impact_param / rho

    amplification_fspl = np.zeros(len(amplification_pspl))

    # Far from the lens (z_yoo>>1), then PSPL.
    indexes_PSPL = np.where((z_yoo > yoo_table[0][-1]))[0]

    amplification_fspl[indexes_PSPL] = amplification_pspl[indexes_PSPL]

    # Very close to the lens (z_yoo<<1), then Witt&Mao limit.
    indexes_WM = np.where((z_yoo < yoo_table[0][0]))[0]

    amplification_fspl[indexes_WM] = amplification_pspl[indexes_WM] * \
                                     (2 * z_yoo[indexes_WM] - gamma * (2 - 3 * np.pi / 4) * z_yoo[indexes_WM])

    # FSPL regime (z_yoo~1), then Yoo et al derivatives
    indexes_FSPL = np.where((z_yoo <= yoo_table[0][-1]) & (z_yoo >= yoo_table[0][0]))[0]

    amplification_fspl[indexes_FSPL] = amplification_pspl[indexes_FSPL] * \
                                       (yoo_table[1](z_yoo[indexes_FSPL]) - gamma * yoo_table[2](z_yoo[indexes_FSPL]))

    return amplification_fspl


def Jacobian_amplification_FSPL(tau, uo, rho, gamma, yoo_table):
    """Same function as above, just also returns the impact parameter needed for the Jacobian FSPL model.
    The Yoo et al. Finite Source Point Lens magnification and the impact parameter U(t).
    "OGLE-2003-BLG-262: Finite-Source Effects from a Point-Mass Lens",Yoo, J. et al 2004
    http://adsabs.harvard.edu/abs/2004ApJ...603..139Y

    :param array_like tau: the tau define for example in
                               http://adsabs.harvard.edu/abs/2015ApJ...804...20C

    :param array_like uo: the uo define for example in
                             http://adsabs.harvard.edu/abs/2015ApJ...804...20C

    :param float rho: the normalised angular source star radius

    :param float gamma: the microlensing limb darkening coefficient.

    :param array_like yoo_table: the Yoo et al. 2004 table approximation. See microlmodels for more details.

    :return: the FSPL magnification A_FSPL(t) and the impact parameter U(t)
    :rtype: tuple, tuple of two array_like
    """
    impact_param = impact_parameter(tau, uo)  # u(t)
    impact_param_square = impact_param ** 2  # u(t)^2

    amplification_pspl = (impact_param_square + 2) / (impact_param * (impact_param_square + 4) ** 0.5)

    z_yoo = impact_param / rho

    amplification_fspl = np.zeros(len(amplification_pspl))

    # Far from the lens (z_yoo>>1), then PSPL.
    indexes_PSPL = np.where((z_yoo > yoo_table[0][-1]))[0]

    amplification_fspl[indexes_PSPL] = amplification_pspl[indexes_PSPL]

    # Very close to the lens (z_yoo<<1), then Witt&Mao limit.
    indexes_WM = np.where((z_yoo < yoo_table[0][0]))[0]

    amplification_fspl[indexes_WM] = amplification_pspl[indexes_WM] * \
                                     (2 * z_yoo[indexes_WM] - gamma * (2 - 3 * np.pi / 4) * z_yoo[indexes_WM])

    # FSPL regime (z_yoo~1), then Yoo et al derivatives
    indexes_FSPL = np.where((z_yoo <= yoo_table[0][-1]) & (z_yoo >= yoo_table[0][0]))[0]

    amplification_fspl[indexes_FSPL] = amplification_pspl[indexes_FSPL] * \
                                       (yoo_table[1](z_yoo[indexes_FSPL]) - gamma * yoo_table[2](z_yoo[indexes_FSPL]))

    return amplification_fspl, impact_param


def amplification_USBL(separation, mass_ratio, x_source, y_source, rho):
    """
    The Uniform Source Binary Lens amplification, based on the work of Valerio Bozza, thanks :)
    "Microlensing with an advanced contour integration algorithm: Green's theorem to third order, error control,
    optimal sampling and limb darkening ",Bozza, Valerio 2010. Please cite the paper if you used this.
    http://mnras.oxfordjournals.org/content/408/4/2188

    :param array_like separation: the projected normalised angular distance between the two bodies
    :param float mass_ratio: the mass ratio of the two bodies
    :param array_like x_source: the horizontal positions of the source center in the source plane
    :param array_like y_source: the vertical positions of the source center in the source plane
    :param float rho: the normalised (to :math:`\\theta_E') angular source star radius
    :param float tolerance: the relative precision desired in the magnification

    :return: the USBL magnification A_USBL(t)
    :rtype: array_like
    """

    amplification_usbl = []


    for xs, ys, s in zip(x_source, y_source, separation):

        magnification_VBB = VBB.BinaryMag2(s, mass_ratio, xs, ys, rho)

        amplification_usbl.append(magnification_VBB)



    return np.array(amplification_usbl)


def amplification_FSBL(separation, mass_ratio, x_source, y_source, rho, limb_darkening_coefficient):
    """
    The Uniform Source Binary Lens amplification, based on the work of Valerio Bozza, thanks :)
    "Microlensing with an advanced contour integration algorithm: Green's theorem to third order, error control,
    optimal sampling and limb darkening ",Bozza, Valerio 2010. Please cite the paper if you used this.
    http://mnras.oxfordjournals.org/content/408/4/2188

    :param array_like separation: the projected normalised angular distance between the two bodies
    :param float mass_ratio: the mass ratio of the two bodies
    :param array_like x_source: the horizontal positions of the source center in the source plane
    :param array_like y_source: the vertical positions of the source center in the source plane
    :param float limb_darkening_coefficient: the linear limb-darkening coefficient
    :param float rho: the normalised (to :math:`\\theta_E') angular source star radius

    :param float tolerance: the relative precision desired in the magnification

    :return: the USBL magnification A_USBL(t)
    :rtype: array_like
    """

    amplification_fsbl = []

    for xs, ys, s in zip(x_source, y_source, separation):
        # print index,len(Xs)
        # print s,q,xs,ys,rho,tolerance
        magnification_VBB = VBB.BinaryMagDark(s, mass_ratio, xs, ys, rho, limb_darkening_coefficient, VBB.Tol)

        amplification_fsbl.append(magnification_VBB)



    return np.array(amplification_fsbl)


def amplification_PSBL(separation, mass_ratio, x_source, y_source):
    """
    The Point Source Binary Lens amplification, based on the work of Valerio Bozza, thanks :)
    "Microlensing with an advanced contour integration algorithm: Green's theorem to third order, error control,
    optimal sampling and limb darkening ",Bozza, Valerio 2010. Please cite the paper if you used this.
    http://mnras.oxfordjournals.org/content/408/4/2188

    :param array_like separation: the projected normalised angular distance between the two bodies
    :param float mass_ratio: the mass ratio of the two bodies
    :param array_like x_source: the horizontal positions of the source center in the source plane
    :param array_like y_source: the vertical positions of the source center in the source plane

    :return: the PSBL magnification A_PSBL(t)
    :rtype: array_like
    """

    amplification_psbl = []


    for xs, ys, s in zip(x_source, y_source, separation):

        magnification_VBB =VBB.BinaryMag0(s, mass_ratio, xs, ys)

        amplification_psbl.append(magnification_VBB)

    return np.array(amplification_psbl)



def amplification_FSPL_for_Lyrae(tau, uo, rho, gamma, yoo_table):
    """
    The Yoo et al Finite Source Point Lens magnification.
    "OGLE-2003-BLG-262: Finite-Source Effects from a Point-Mass Lens",Yoo, J. et al 2004
    http://adsabs.harvard.edu/abs/2004ApJ...603..139Y

    :param array_like tau: the tau define for example in
                                   http://adsabs.harvard.edu/abs/2015ApJ...804...20C

    :param array_like uo: the uo define for example in
                                 http://adsabs.harvard.edu/abs/2015ApJ...804...20C

    :param float rho: the normalised angular source star radius

    :param float gamma: the microlensing limb darkening coefficient.

    :param array_like yoo_table: the Yoo et al. 2004 table approximation. See microlmodels for more details.

    :return: the FSPL magnification A_FSPL(t)
    :rtype: array_like
    """
    impact_param = impact_parameter(tau, uo)  # u(t)
    impact_param_square = impact_param ** 2  # u(t)^2

    amplification_pspl = (impact_param_square + 2) / (impact_param * (impact_param_square + 4) ** 0.5)

    z_yoo = impact_param / rho

    amplification_fspl = np.zeros(len(amplification_pspl))

    # Far from the lens (z_yoo>>1), then PSPL.
    indexes_PSPL = np.where((z_yoo > yoo_table[0][-1]))[0]

    amplification_fspl[indexes_PSPL] = amplification_pspl[indexes_PSPL]

    # Very close to the lens (z_yoo<<1), then Witt&Mao limit.
    indexes_WM = np.where((z_yoo < yoo_table[0][0]))[0]

    amplification_fspl[indexes_WM] = amplification_pspl[indexes_WM] * \
                                     (2 * z_yoo[indexes_WM] - gamma[indexes_WM] * (2 - 3 * np.pi / 4) * z_yoo[
                                         indexes_WM])

    # FSPL regime (z_yoo~1), then Yoo et al derivatives
    indexes_FSPL = np.where((z_yoo <= yoo_table[0][-1]) & (z_yoo >= yoo_table[0][0]))[0]

    amplification_fspl[indexes_FSPL] = amplification_pspl[indexes_FSPL] * \
                                       (yoo_table[1](z_yoo[indexes_FSPL]) - gamma[indexes_FSPL] * yoo_table[2](
                                           z_yoo[indexes_FSPL]))

    return amplification_fspl
