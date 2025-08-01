#!/usr/bin/env python3
"""
significance.py

A utility module for comparing an observed proportion against a set baseline using a binomial test.
"""

from scipy.stats import binomtest

class SignificanceTester:
    """
    Tests whether an observed proportion differs from the
    reference proportion via a binomial test.
    """

    def __init__(self, reference_proportion):
    
        self.reference_proportion = reference_proportion

    def test_significance(self, successes, trials, alternative='two-sided'):
        """
        Perform a binomial test to compare the observed proportion (successes/trials)
        to the reference proportion.
        """
        result = binomtest(
            k=successes,
            n=trials,
            p=self.reference_proportion,
            alternative=alternative
        )
        return result.pvalue

    def is_below_05(self, successes, trials, alternative='two-sided'):
        """
        Check whether the null hypothesis should be rejected, 
        i.e. whether the probability the result is due to chance is less than 5%.
        """
        p_value = self.test_significance(successes, trials, alternative)
        return p_value < 0.05
    

if __name__ == '__main__':
    # Initialize tester with default reference proportion (9.7%)
    tester = SignificanceTester()
    
    # For proportion test, assume 100 trials for demonstration
    #n_trials = 1445
    #n_successes = 428
    n_trials = 566
    n_successes = 58
    percent = n_successes / n_trials * 100
    
    p_value = tester.test_significance(n_successes, n_trials)
    is_significant = tester.is_below_05(n_successes, n_trials)
    
    print(f"Testing {percent:.2f}% against reference {tester.reference_proportion*100}%")
    print(f"p-value: {p_value:.10f}")
    print(f"Statistically significant: {is_significant}")
    print(f"{'Reject' if is_significant else 'Cannot reject'} null hypothesis")

    