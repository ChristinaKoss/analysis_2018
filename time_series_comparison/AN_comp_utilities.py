# Includes functions used to assess similarity of time series provided

# Weather can be though of as a non-stationary object in high dimensional space.
# Specific trajectories on this space correspond to specific realisations of weather
# conditions (temperature, wind, humidity and plenty more) across time.
# The perfect weather prediction machine recreates this high dimensional space, and
# can thus predict the unfolding of the different phenomena. However, weather is a
# chaotic system, meaning that small differences in initial conditions can lead to huge
# differences in the way the phenomena evolve as time passes. ALso, it is a non-
# stationary system, meaning that the statistics affecting the form of the high-dimensional
# object change with time.

# Since it is so difficult to reconstruct this whole space, predictive models try
# to reduce it. Also, the ultimate goal is to have a comprehensive picture of
# specific variables, like the temperature, which can be reported and understood by people.
# So, the assessment of whether a particular model is good or bad makes sense only in
# the low dimensional space of general interest. Ultimately, we want to receive a one dimensional
# time series created by a certain predictive model, compare it to the real data,
# and tell whether the prediction was good enough.

# Defining what is a good prediction can be quite complex and depends on human factors
# (for example, how much a 10 % difference in humidity affects felt temperature?) that
# are not available to us. The goal here is to provide a framework of different techniques
# and measures, and also characterize each one in terms of what errors it punishes more
# or less severely.

# Interesting article: http://dbgroup.eecs.umich.edu/files/sigmod07timeseries.pdf
# The aforementioned point also stated in the article: " Time
# series simularity methods can be used for computing trajectory similarity"
# http://www.cs.ust.hk/~leichen/pub/04/vldb04.pdf
# if triangular identity doesn't hold then distance stops being a local feature, so
# is doesn't make sense to compare distances (maybe there are better paths)

# DTW measures a distance-like quantity between two given sequences, but it doesn't guarantee the triangle inequality to hold.

# https://infolab.usc.edu/csci599/Fall2003/Time%20Series/Efficient%20Similarity%20Search%20In%20Sequence%20Databases.pdf
# "The euclidean distance measure is the optimal distance measure for estimation if the signals are corrupted by Gaussian, additive noise."

# To introduce a measure that is independent of the length of the data we are trying
# to predict, a way to find how the maximum of a gaussian noise array is changing
# relating to the size of the array. For sure the dependence on n is quite weak,
# especially as n grows a lot (sqrt(n) was tried but it is too fast). Not sure if
# such a prediction exists at all

# Grigoriy Vevyurko found the solution:
# https://math.stackexchange.com/questions/89030/expectation-of-the-maximum-of-gaussian-random-variables
# find the probability distibution of all measurements being below a value, then the complementary, then get the pdf and finaly compute the mean
# on this and use it to scale the measure

import numpy as np
from scipy.stats import norm
import scipy, scipy.stats
import matplotlib.pyplot as plt
from sklearn.metrics import log_loss
import math

def compare_time_series(prediction, true, days_ahead, method, data_type = 'temperature', num_excuse = 0, threshold = 0):
    """
    Compares predicted and true time series and produces a measure of similarity.
    This measure can judge how good the prediction was.

    Input:
    -prediction : array of length n with predicted values for a specific number of days ahead
    -true : array of same length n with true values
    -days_ahead : how many days ahead was the prediction made? Final measure is weighted with this
    -method : measure of similarity used
    -data_type : data type of arrays. Changes the way the measure of similarity is scaled.
    Could be 'temperature' in degrees Celcius, 'humidity' as a percentage,
    'precipitation' in mm, 'wind' in km/h or 'prob_rain' in percent (boolean matrix for true)
    -num_excuse : number of biggest outliers to be removed before computing the measures
    -threshold : difference in corresponding values that is deamed to be unacceptable

    Output:
    -measure : a measure of similarity as a single number between 0 and 1. scaling of the measure
    is method-dependent, so it will be done inside the function for each method
    -value : the exact value of the measure used, if such exists (unbiased measure)
    -differences: point-wise differences for plotting purposes
    -perc_over : percentage of measurements that different more that the acceptable threshold

    It is important to tell apart the predicted time series from the true one,
    because not all measures of similarity are symmetric (non-metric operators)
    """
    supports_neg = ['temperature']

    if len(prediction) != len(true):
        print('Arrays to be compared do not have the same length!')
        return 0

    prediction, true = preprocess(prediction, true, not (data_type in supports_neg))

    pred, tr, ind = excuse(prediction, true, num_excuse)
    measure, value = method(pred, tr, data_type)

    # here a way to scale measure based on days_ahead (independently of data_type?)
    # bends the measure which is between 0 and 1 so that prediction of many days ahead
    # with the same performance based on 'method' are viewed in a better light
    # maybe fourth root is a little bit harsh

    measure = measure ** np.power(days_ahead,1/4)

    if data_type == 'prob_rain':
        # convert to percents
        true = true*100

    differences = prediction - true

    perc_over = 0
    if threshold > 0:
        over = abs(differences) > threshold
        perc_over = sum(over)/len(over)

    return measure, value, differences, perc_over


def preprocess(prediction, true, discard_neg = 0):
    """General preprocessing considerations.

    -Removes NaN values.
    -Removes negative values when data type does not support negative values.
    """

    ind = []
    for i in range(len(prediction)):
        if math.isnan(prediction[i]) or math.isnan(true[i]) or (discard_neg and (prediction[i]<0 or true[i]<0)):
            ind.append(i)

    if ind:
        prediction =  np.delete(prediction, ind)
        true =  np.delete(true, ind)

    return prediction, true


def variance(prediction, true, data_type):
    """Finds variance as a global descriptive measure of similarity"""

    var = np.sqrt( ((prediction - true) ** 2).mean() )
    # scale variance by mean
    measure = var/true.mean()
    # scale result according to what data type we have
    if data_type == 'temperature':
        b = 2
    elif data_type == 'humidity':
        b = 3
    elif data_type == 'wind':
        b = 2
    elif data_type == 'precipitation':
        b = .6
    else:
        print('Not appropriate data type!')
    # convert result to a value between 0 and 1, using tanh
    measure = np.tanh(b*measure)

    return measure, var


def norm1(prediction, true, data_type):
    """
    Find first norm as a global descriptive measure of similarity.
    Punishes outliers less severely, not the optimal choice if the difference
    signal is gaussian noise (which it should be)
    """

    norm = abs(prediction - true).mean()
    # scale variance by mean
    measure = norm/true.mean()
    # scale result according to what data type we have
    if data_type == 'temperature':
        b = 2.5
    elif data_type == 'humidity':
        b = 4
    elif data_type == 'wind':
        b = 2.5
    elif data_type == 'precipitation':
        b = .8
    else:
        print('Not appropriate data type!')
        return 0
    # convert result to a value between 0 and 1, using tanh
    measure = np.tanh(b*measure)

    return measure, norm


def outlier(prediction, true, data_type):
    """
    Finds the biggest outlier as a local descriptive measure of similarity.
    With weather, we are interested in a model that is not necessarily very exact,
    but when it fails it does not fail hard. For example, we do not want a prediction
    for a single day to be zero precipitation, and it turns out raining, even if this model
    is near perfect for the other days
    """

    outlier = max(abs(prediction-true))
    # unbiased variance estimator
    n = len(prediction)
    var_est = np.var(prediction-true,ddof = 1)
    # expected outlier if we assume that the difference is gaussian noise
    exp_outlier = var_est*np.sqrt(np.log10(n**2/(2*np.pi*np.log10(n**2/(2*np.pi)))))*(1+0.577/np.log10(n))
    # scale outlier by expected outlier for this size of arrays
    outlier_sc = outlier*(4*var_est/exp_outlier)
    # scale outlier by mean
    measure = outlier_sc/true.mean()
    # scale result according to what data type we have
    if data_type == 'temperature':
        b = .5
    elif data_type == 'humidity':
        b = 1
    elif data_type == 'wind':
        b = .5
    elif data_type == 'precipitation':
        b = .3
    else:
        print('Not appropriate data type!')
        return 0
    # convert result to a value between 0 and 1, using tanh
    measure = np.tanh(b*measure)

    return measure, outlier


def cross_entropy(prediction, true, data_type):
    if data_type == 'prob_rain':
        b = .02
    else:
        print('Not appropriate data type!')
        return 0

    c_entropy =  log_loss(true,prediction,normalize=True)

    # convert result to a value between 0 and 1, using tanh
    measure = np.tanh(b*c_entropy)
    return measure, c_entropy


def convert_rainfall(prob_rain,mean,variance):
    """
    This function will probably will not be used since we have data from both
    probabilities and mm

    -prob_rain is the probability of rain as predicted by the weather forecast
    -mean is the mean rainfall in mm (for the month?), taken fron the data or computed on the data
    for this specific station
    -variance is the variance of the rainfall in mm for the month
    """
    # fit with a gaussian distribution
    rainfall = mean + variance*norm.ppf(prob_rain)
    # limit values to logical ones
    rainfall = max(min(rainfall, mean + 3*variance), 0)
    if prob_rain<.1:
        rainfall = 0
    return rainfall


def histogram_probability_of_rain(prob_rain,true):
    """
    Compares the forecasted probability of rain histogram with then
    actual boolean outcomes (rain or no rain) the next day. It does not make a distinction
    based on how much (in mm) it rained!

    The days should be picked so that the prediction is within a certain % interval (eg 5-15 %)
    and see how the bernolli with p = days with rain/total days looks like.

    -prob_rain is the probability of rain as predicted by the weather forecast
    -true is the array of boolean values that denote if it rained or not it the corresponding day

    Returns binomial distribution and prob_rain, ready to plot.
    """
    # Compute the probability of rain at any given day
    if len(true)==0:
        return 0
    p = np.count_nonzero(true)/len(true)
    x = scipy.linspace(0,len(true),len(true)+1)
    pmf = scipy.stats.binom.pmf(x,len(true),p)
    pmf = pmf*len(true)
    plt.figure()
    plt.plot(x/len(true),pmf)
    prob_rain = prob_rain/100
    plt.hist(prob_rain,len(true)//10+1,normed='True')
    return prob_rain, pmf


def plot_histograms_rain(prob_rain,true):
    """ Example of running histogram_probability_of_rain for certain intervals """

    intervals = [0,5,15,25,35,45,55,65,75,85,95,100]

    for i in range(len(intervals)-1):
        mask = np.logical_and(prob_rain>intervals[i],prob_rain<intervals[i+1])
        histogram_probability_of_rain(prob_rain[mask],true[mask])
    return 0


def excuse(prediction, true, num_excuse):
    """
    Removes measurements that have the biggest difference between the predicted and true time series
    Allows assessment of time series prediction independent of possible local abnormalities of
    the prediction (eg caused by an extreme weather condition that was not accounted for in the model)
    or outliers in general

    Returns predicted and true time series without these measurements
    """
    if num_excuse == 0:
        return prediction, true, -1

    abs_diff = abs(prediction - true)
    ind = abs_diff.argsort()[-num_excuse:][::-1]
    prediction =  np.delete(prediction, ind)
    true =  np.delete(true, ind)
    return prediction, true, ind


def fit_distr(data,data_type = 'temperature',fit_with='norm'):
    """
    Fits a predifined distribution to the data. Used to fit a distribution on the difference of
    predicted - true data, and plot the result

    -data is the difference of predicted - true data
    -data type can be 'temperature' in degrees Celcius, 'humidity' as a percentage,
    'precipitation' in mm, 'wind' in km/h

    Returns the fitted distribution pdf_fitted and a vector x to plot on the x axis
    """

    if data_type == 'temperature':
        xlabel = 'Temperature [degrees Celcius]'
    elif data_type == 'humidity':
        xlabel = 'Humidity [%]'
    elif data_type == 'wind':
        xlabel = 'Wind speed [km/h]'
    elif data_type == 'precipitation':
        xlabel = 'Precipitation [mm/m^2]'

    x = np.linspace(min(data),max(data),num=1000)
    size = len(x)
    h = plt.hist(data, bins=np.linspace(min(data), max(data), len(data)//100), normed = 'True')

    dist = getattr(scipy.stats, fit_with)
    param = dist.fit(data)
    pdf_fitted = dist.pdf(x, *param[:-2], loc=param[-2], scale=param[-1])
    plt.plot(x,pdf_fitted, label=fit_with)
    plt.legend(loc='upper right')
    plt.xlabel(xlabel)
    plt.title('Distribution of difference between prediction and true value')
    plt.show()
    return x, pdf_fitted
