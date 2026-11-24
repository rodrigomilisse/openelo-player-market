// Least-squares line through a series: value at step i is mean + slope * (i - middle).
export function fitTrend(values) {
  const middle = (values.length - 1) / 2;
  const mean = values.reduce((sum, v) => sum + v, 0) / values.length;
  let covariance = 0;
  let variance = 0;
  values.forEach((v, i) => {
    covariance += (i - middle) * (v - mean);
    variance += (i - middle) * (i - middle);
  });
  return { mean, middle, slope: covariance / variance };
}
