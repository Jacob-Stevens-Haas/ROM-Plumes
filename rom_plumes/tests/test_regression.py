from typing import cast

import numpy as np
import pytest

from ..models import PLUME
from ..regressions import _tildify
from ..regressions import _untildify
from ..regressions import do_inv_quadratic_regression
from ..regressions import do_parametric_regression
from ..regressions import do_polynomial_regression
from ..regressions import do_sinusoid_regression
from ..regressions import edge_regression
from ..regressions import regress_frame_mean
from ..typing import Float1D
from ..typing import Frame
from ..typing import X_pos
from ..typing import Y_pos


def test_regress_multiframe_mean():
    regress_multiframe_mean = PLUME.regress_multiframe_mean
    expected = np.array([[1, 2, 3, 4], [4, 3, 2, 1]])
    a, b, c, d = expected[0]
    e, f, g, h = expected[1]

    def poly1(t):
        return a * t**3 + b * t**2 + c * t + d

    def poly2(t):
        return e * t**3 + f * t**2 + g * t + h

    slice = 4
    R = np.linspace(0, 1, 101)

    mean_points_1 = np.vstack((R, R, poly1(R))).T
    mean_points_2 = np.vstack((R, R, poly2(R))).T

    mean_points = [(1, mean_points_1[::slice, :]), (2, mean_points_2[::slice, :])]

    result = regress_multiframe_mean(mean_points, "poly", 3)

    np.testing.assert_array_almost_equal(expected, result)


def test_regress_multiframe_mean_decenter():
    regress_multiframe_mean = PLUME.regress_multiframe_mean
    expected = np.array([[1, 2, 3, 4], [4, 3, 2, 1]])
    a, b, c, d = expected[0]
    e, f, g, h = expected[1]

    def poly1(t):
        return a * t**3 + b * t**2 + c * t + d

    def poly2(t):
        return e * t**3 + f * t**2 + g * t + h

    slice = 4
    R = np.linspace(0, 1, 101)
    mean_points_1 = np.vstack((R, R, poly1(R))).T
    mean_points_2 = np.vstack((R, R, poly2(R))).T

    mean_points = [(1, mean_points_1[::slice, :]), (2, mean_points_2[::slice, :])]

    origin = (10, 10)
    mean_points_1[:, 1:] += origin
    mean_points_2[:, 1:] += origin
    mean_points = [(1, mean_points_1[::slice, :]), (2, mean_points_2[::slice, :])]

    result = regress_multiframe_mean(mean_points, "poly", 3, decenter=origin)
    np.testing.assert_array_almost_equal(expected, result)


def test_regress_multiframe_mean_poly_para():
    regress_multiframe_mean = PLUME.regress_multiframe_mean
    expected = np.array([[1, 2, 3, 4], [4, 3, 2, 1]])
    a, b, c, d = expected[0]
    e, f, g, h = expected[1]

    def poly1(t):
        return a * t**3 + b * t**2 + c * t + d

    def poly2(t):
        return e * t**3 + f * t**2 + g * t + h

    slice = 4
    R = np.linspace(0, 1, 101)

    # test poly_para
    mean_points_1 = np.vstack((R, poly1(R), poly2(R))).T
    mean_points_2 = np.vstack((R, poly2(R), poly1(R))).T

    mean_points = [(1, mean_points_1[::slice, :]), (2, mean_points_2[::slice, :])]
    result = regress_multiframe_mean(mean_points, "poly_para", 3)

    np.testing.assert_array_almost_equal(
        np.hstack((expected[0], expected[1])), result[0]
    )
    np.testing.assert_array_almost_equal(
        np.hstack((expected[1], expected[0])), result[1]
    )


def test_regress_multiframe_mean_poly_para_nan():
    regress_multiframe_mean = PLUME.regress_multiframe_mean
    expected = np.array([[1, 2, 3, 4], [4, 3, 2, 1]])
    a, b, c, d = expected[0]
    e, f, g, h = expected[1]

    def poly1(t):
        return a * t**3 + b * t**2 + c * t + d

    def poly2(t):
        return e * t**3 + f * t**2 + g * t + h

    slice = 4
    R = np.linspace(0, 1, 101)
    mean_points_1 = np.vstack((R, poly1(R), poly2(R))).T
    mean_points_2 = np.vstack((R, poly2(R), poly1(R))).T

    # test poly_para nan
    mean_points = [
        (1, mean_points_1[::slice, :]),
        (2, mean_points_2[0, :].reshape(1, 3)),
    ]
    result = regress_multiframe_mean(mean_points, "poly_para", 3)

    np.testing.assert_array_almost_equal(
        np.hstack((expected[0], expected[1])), result[0]
    )
    np.testing.assert_array_almost_equal(
        np.array([np.nan for _ in range(8)]), result[1]
    )


def test_regress_mean_points_k():
    # linear
    slise = 4
    R = np.linspace(0, 1, 101)
    mean_points = np.vstack((R, R, R)).T

    expected = (1, 0)
    result = regress_frame_mean(mean_points[::slise, :], method="linear")
    np.testing.assert_array_almost_equal(expected, result)

    # poly
    expected = (1, 2, 3)
    a, b, c = expected

    def poly_func(x):
        return a * x**2 + b * x + c

    mean_points = np.vstack((R, R, poly_func(R))).T
    result = regress_frame_mean(mean_points[::slise, :], method="poly")
    np.testing.assert_array_almost_equal(expected, result)

    # poly_inv - require lower branch of sqrt
    mean_points = np.vstack((R, poly_func(R), -R)).T
    result = regress_frame_mean(mean_points[::slise, :], method="poly_inv")
    np.testing.assert_array_almost_equal(expected, result)

    # poly_para
    expected = (1, 2, 3, 4, 4, 3, 2, 1)

    a, b, c, d, e, f, g, h = expected

    def poly1(t):
        return a * t**3 + b * t**2 + c * t + d

    def poly2(t):
        return e * t**3 + f * t**2 + g * t + h

    R = np.linspace(0, 1, 101)

    mean_points = np.vstack((R, poly1(R), poly2(R))).T

    result = regress_frame_mean(mean_points[::slise, :], method="poly_para", poly_deg=3)

    np.testing.assert_array_almost_equal(expected, result)


def test_do_polynomial_regression():
    expected = (1, 2, 3)
    poly_deg = 2
    a, b, c = expected

    def poly_func(x):
        return a * x**2 + b * x + c

    x = np.linspace(0, 1, 101)
    y = poly_func(x)

    step = 4
    result = do_polynomial_regression(x[::step], y[::step], poly_deg=poly_deg)
    np.testing.assert_almost_equal(expected, result)


def test_do_polynomial_regression_insufficient_points():
    expected = (1, 2, 3)
    poly_deg = 4
    a, b, c = expected

    def poly_func(x):
        return a * x**2 + b * x + c

    x = np.linspace(0, 1, 101)
    y = poly_func(x)

    with pytest.raises(np.linalg.LinAlgError):
        do_polynomial_regression(x[:3], y[:3], poly_deg=poly_deg)


def test_do_sinusoid_regression():
    expected = (1, 2, 3, 4)
    a, w, g, b = expected

    def sinusoid_func(t, r):
        return a * np.sin(w * r - g * t) + b * r

    axis = np.linspace(0, 1, 101)
    tt, rr = np.meshgrid(axis, axis)

    X = np.hstack((tt.reshape(-1, 1), rr.reshape(-1, 1)))
    Y = sinusoid_func(tt, rr).reshape(-1)

    step = 4
    result = do_sinusoid_regression(X[::step], Y[::step], (1, 1, 1, 1))

    np.testing.assert_array_almost_equal(expected, result)


def test_do_parametric_regression():
    expected = (1, 2, 3, 4, 4, 3, 2, 1)

    a, b, c, d, e, f, g, h = expected

    def poly1(t):
        return a * t**3 + b * t**2 + c * t + d

    def poly2(t):
        return e * t**3 + f * t**2 + g * t + h

    X = np.linspace(0, 1, 101)
    Y = np.hstack((poly1(X).reshape(-1, 1), poly2(X).reshape(-1, 1)))

    result = do_parametric_regression(X, Y, poly_deg=3)

    np.testing.assert_array_almost_equal(expected, result)


def test_edge_regression_linear():
    expected = (1, 2, 3)
    np.random.seed(1)

    t_feat = np.random.rand(100)
    x_feat = np.random.rand(100)

    X = np.vstack((t_feat, x_feat)).T
    Y = expected[0] + expected[1] * t_feat + expected[2] * x_feat

    result = edge_regression(X, Y, regression_method="linear")

    np.testing.assert_array_almost_equal(expected, result)


@pytest.mark.parametrize(
    argnames=["coef0"],
    argvalues=[
        (None,),
        (np.array([-1.0, 1e0, 1e0]),),
    ],
)
def test_inv_quad_regression(coef0):
    # y=-x^2
    true_data = np.array(
        [
            [0, 0],
            [-0.25, 0.5],
            [-1, 1],
            [-4, 2],
        ],
        dtype=float,
    )
    X = true_data[:, 0]
    Y = true_data[:, 1]
    true_abc = np.array([-1, 0, 0])

    coef_solve = do_inv_quadratic_regression(X, Y, coef0)

    np.testing.assert_allclose(true_abc, coef_solve, atol=1e-4)


def test_untildify():
    coef = np.random.rand(3)
    result = _tildify(_untildify(cast(Float1D, coef)))
    np.testing.assert_allclose(result, coef)
    result2 = _untildify(_tildify(cast(Float1D, coef)))
    np.testing.assert_allclose(result2, coef)


def test_plume_center_regression_doesnt_mutate():
    mean_points = [(Frame(0), np.array([[1, 1, 1], [2, 2, 2]]))]
    mean_point_arr_copy = np.copy(mean_points[0][1])
    PLUME.regress_multiframe_mean(
        mean_points=mean_points,
        regression_method="linear",
        decenter=(X_pos(1), Y_pos(1)),
    )
    np.testing.assert_array_equal(mean_points[0][1], mean_point_arr_copy)
