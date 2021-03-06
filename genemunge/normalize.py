import os
import pandas
import numpy
import pickle
import warnings
from pathlib import Path
from cytoolz import partial

from . import convert
from . import describe

def do_nothing(data):
    """
    A function that does nothing.

    Args:
        Anything

    Returns:
        Anything

    """
    return data


def deduplicate(data):
    """
    Adds the values from any duplicated genes.

    Args:
        data (pandas.DataFrame ~ (num_samples, num_genes))

    Returns:
        pandas.DataFrame

    """
    return data.groupby(data.columns, axis=1).sum()


def impute(data, scale=0.5):
    """
    Replace any zeros in each row with a fraction of the smallest non-zero
    value in the corresponding row.

    Args:
        data (pandas.DataFrame ~ (num_samples, num_genes))
        scale (optional; float)

    Returns:
        imputed data (pandas.DataFrame ~ (num_samples, num_genes))

    """
    v = scale * data[data > 0].min(axis=1)
    data_fill = data.fillna(0)
    return data_fill + (data_fill == 0).multiply(v, axis=0)


class Normalizer(object):
    """
    Tools to change units of expression data, primarily to convert to TPM.

    Attributes:
        gene_lengths (DataFrame): bp lengths for genes.

    """
    def __init__(self, identifier='symbol'):
        """
        Tools to normalize expression data and transform into TPM.

        Args:
            identifier (str)

        Returns:
            Normalizer

        """
        # read the gene lengths
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'gtex')
        gene_info = pandas.read_csv(os.path.join(p, 'gene_info.csv'), sep='\t')
        gene_info.set_index('gene_id', inplace=True)
        self.gene_lengths = gene_info['bp_length']
        # clean the ensemble gene ids
        self.gene_lengths.index = convert.clean_ensembl_ids(self.gene_lengths.index)
        self.gene_lengths = self.gene_lengths[~self.gene_lengths.index.duplicated(keep='first')]
        # convert the gene ids
        self.converter = None
        if identifier is not 'ensembl_gene_id':
            self.converter = convert.IDConverter('ensembl_gene_id', identifier)
            self.gene_lengths.index = self.converter.convert_list(list(self.gene_lengths.index))
        self.describer = describe.Describer(identifier)
        # drop any NaN and duplicate ids
        self.gene_lengths = self.gene_lengths[~self.gene_lengths.index.isnull()]
        self.gene_lengths = self.gene_lengths[~self.gene_lengths.index.duplicated(keep='first')]

    def _get_common_genes(self, gene_list):
        """
        Get a set of identifiers that occur in GTEx and, therefore,
        have gene lengths.

        Args:
            gene_list (List[str])

        Returns:
            common_genes (List[str])

        """
        if gene_list is None:
            # reindex to all of the gtex genes
            return list(self.gene_lengths.index)
        # select the genes in the gene_list that also occur in gtex
        common_genes = [gene for gene in gene_list if gene in self.gene_lengths.index]
        # warn the user about any genes that are not in gtex and are being dropped
        missing_genes = list(set(gene_list) - set(common_genes))
        if len(missing_genes) > 0:
            warnings.warn("Could not find identifiers: {}".format(missing_genes))
        return common_genes

    def reindex(self, data, gene_list=None):
        """
        Reindexes the dataframe so that it has the same genes as the gtex
        dataset from recount.

        Args:
            data (pandas.DataFrame ~ (num_samples, num_genes)): any expression data
            gene_list (List[str]): a list of gene ids

        Returns:
            pandas.DataFrame ~ (num_samples, num_common_genes)

        """
        common_genes = self._get_common_genes(gene_list)
        common = data.reindex(columns=common_genes)
        common.fillna(0, inplace=True)
        return common

    def tpm_from_rpkm(self, data, gene_list=None, imputer=do_nothing):
        """
        Transform data from RPKM to TPM.
        Unless a gene list is specified, genes are reindex to GTEx:
            - Any genes from GTEx that are not in data.columns are set to zero.
            - Any genes not present in GTEx are dropped.
        Takes an optional imputation method applied after reindexing.

        Args:
            data (pandas.DataFrame ~ (num_samples, num_genes)): RPKM data
            gene_list (optional; List[str]): a list of gene ids
            imputer (optional; callable)

        Returns:
            pandas.DataFrame

        """
        subset = imputer(self.reindex(data, gene_list))
        return 10**6 * subset.divide(subset.sum(axis=1), axis='index')

    def tpm_from_counts(self, data, gene_list=None, imputer=do_nothing):
        """
        Transform data from counts to TPM.
        Unless a gene list is specified, genes are reindex to GTEx:
            - Any genes from GTEx that are not in data.columns are set to zero.
            - Any genes not present in GTEx are dropped.
        Takes an optional imputation method applied after reindexing.

        Args:
            data (pandas.DataFrame ~ (num_samples, num_genes)): count data
            gene_list (optional; List[str]): a list of gene ids
            imputer (optional; callable)

        Returns:
            pandas.DataFrame

        """
        subset = imputer(self.reindex(data, gene_list))
        normed = subset.divide(self.gene_lengths[subset.columns], axis='columns')
        return 10**6 * normed.divide(normed.sum(axis=1), axis='rows')

    def tpm_from_subset(self, data, gene_list=None, imputer=do_nothing):
        """
        Renormalize a subset of genes already in TPM.
        Unless a gene list is specified, genes are reindex to GTEx:
            - Any genes from GTEx that are not in data.columns are set to zero.
            - Any genes not present in GTEx are dropped.
        Takes an optional imputation method applied after reindexing.

        Args:
            data (pandas.DataFrame ~ (num_samples, num_genes)): TPM data
            gene_list (optional; List[str]): a list of gene ids
            imputer (optional; callable)

        Returns:
            pandas.DataFrame

        """
        return self.tpm_from_rpkm(data, gene_list, imputer)

    def clr_from_tpm(self, data, gene_list=None, imputer=do_nothing):
        """
        Compute the centered log ratio transform of data in TPM format.
        Unless a gene list is specified, genes are reindex to GTEx:
            - Any genes from GTEx that are not in data.columns are set to zero.
            - Any genes not present in GTEx are dropped.
        Takes an optional imputation method applied after reindexing.

        Args:
            data (pandas.DataFrame ~ (num_samples, num_genes)): TPM data
            gene_list (optional; List[str]): a list of gene ids
            imputer (optional; callable)

        Returns:
            pandas.DataFrame ~ (num_samples, num_genes)

        """
        imputed = self.tpm_from_subset(data, gene_list, imputer)
        log_transformed = numpy.log(imputed)
        return log_transformed.subtract(log_transformed.mean(axis=1), axis=0)

    def tpm_from_clr(self, data, gene_list=None):
        """
        Compute data in TPM format from centered log ratio transformed data.
        Unless a gene list is specified, genes are reindex to GTEx:
            - Any genes from GTEx that are not in data.columns are set to zero.
            - Any genes not present in GTEx are dropped.

        Args:
            data (pandas.DataFrame ~ (num_samples, num_genes)): CLR data
            gene_list (optional; List[str]): a list of gene ids

        Returns:
            pandas.DataFrame ~ (num_samples, num_genes)

        """
        return self.tpm_from_rpkm(numpy.exp(data), gene_list)

    def alr_from_tpm(self, data, reference_genes, gene_list=None,
                     imputer=do_nothing):
        """
        Compute the additive log ratio transform of data in TPM format.
        This transform normalizes by the geometric mean of the reference genes,
        and drops the reference genes from the data set.

        Args:
            data (pandas.DataFrame ~ (num_samples, num_genes)): TPM data
            reference_genes (List[str]): a list of gene ids to use as the
                references in the ALR transform
            gene_list (optional; List[str]): a list of gene ids
            imputer (optional; callable)

        Returns:
            pandas.DataFrame ~ (num_samples, num_genes - num_reference_genes)

        """
        common_genes = self._get_common_genes(gene_list)
        common_references = [gene for gene in reference_genes if gene in common_genes]
        genes_to_keep = [gene for gene in common_genes if gene not in common_references]
        imputed = self.tpm_from_subset(data, genes_to_keep + common_references, imputer)
        log_transformed = numpy.log(imputed)
        refs = log_transformed[common_references].mean(axis=1)
        return log_transformed[genes_to_keep].subtract(refs, axis=0)

    def z_score_from_clr(self, data, tissues, gene_list=None):
        """
        Compute the z-score of the clr'd tpm data relative to healthy tissue
        in GTEx.

        Args:
            data (pandas.DataFrame ~ (num_samples, num_genes)): CLR data
            tissues (pandas.Series) ~ (num_samples)): tissues of data samples
            gene_list (optional; List[str]): a list of gene ids

        Returns:
            pandas.DataFrame ~ (num_samples, num_genes - num_reference_genes)

        """
        # get the clr tissue stats from GTEx
        mean_clr = self.describer.tissue_stats['mean_clr']
        std_clr = self.describer.tissue_stats['std_clr']

        # convert gene IDs from Ensembl to the identifier, if needed
        # duplicates are dropped!
        if self.converter is not None:
            mean_clr.index = self.converter.convert_list(mean_clr.index)
            mean_clr = mean_clr[mean_clr.index.notnull()]
            mean_clr = mean_clr[~mean_clr.index.duplicated(keep='first')]
            std_clr.index = self.converter.convert_list(std_clr.index)
            std_clr = std_clr[std_clr.index.notnull()]
            std_clr = std_clr[~std_clr.index.duplicated(keep='first')]

        if gene_list is None:
            gene_list = data.columns

        mean_clr = mean_clr.reindex(gene_list)
        std_clr = std_clr.reindex(gene_list)

        mean_expression = mean_clr[tissues].transpose().set_index(tissues.index)
        std_expression = std_clr[tissues].transpose().set_index(tissues.index)
        data_subset = self.reindex(data, gene_list)
        return (data_subset - mean_expression)/std_expression

    def ordinalize(self, data, cutoffs, min_value=0):
        """
        Convert data into ordinal values given cutoffs between ordinal boundaries.
        Returns the same type as the input data.

        Example:
            If cutoffs = [-2, 2] and min_value = -1, then
            [[-3.2,  1.4, -0.7]        [[-1,  0,  0]
             [ 2.5, -0.8,  6.1]   ->    [ 1,  0,  1]
             [-1.9, -4.5,  3.7]]        [ 0, -1,  1]]

        Args:
            data (pandas.DataFrame ~ (num_samples, num_genes)): any expression data
            cutoffs (List[float]): cutoffs between ordinal boundaries.
                No lower or upper bounds should be given, e.g. to binarize this
                argument should be a list with 1 value.

        Returns:
            pandas.DataFrame ~ (num_samples, num_genes): ordinal values,
                typed as the input data.

        """
        ordinalizer = partial(numpy.searchsorted, cutoffs)
        return data.apply(ordinalizer).astype(data.dtypes) + min_value


class RemoveUnwantedVariation(object):
    """
    The RUV-2 algorithm.

    Attributes:
        hk_genes (List[str]): a list of housekeeping gene names used in fitting.
        means (pandas.Series): the means of each gene from the training data.
        U (optional; numpy array ~ (num_training_samples, num_factors)):
            left eigenvectors from SVD of housekeeping genes in training set
        L (optional; numpy array ~ (num_factors,))
            eigenvalues from SVD of housekeeping genes in training set
        Vt (optional; numpy_array ~ (num_factors, num_hk_genes)
            right eigenvectors from SVD of housekeeping genes in training set

    """
    def __init__(self, center=True, hk_genes=None, means=None, U=None, L=None, Vt=None):
        """
        Perform the 2-step Remove Unwanted Variation (RUV-2) algorithm
        defined in:

        "Correcting gene expression data when neither the unwanted variation nor the
        factor of interest are observed."
        Biostatistics 17.1 (2015): 16-28.
        Laurent Jacob, Johann A. Gagnon-Bartsch, and Terence P. Speed.

        The algorithm is modified slightly so that batch correction can be
        applied out-of-sample.

        Args:
            center (optional; bool): whether to center the gene means in the fit.
            hk_genes (optional; List[str]): list of housekeeping genes
            means (optional; numpy array ~ (num_genes,))
            U (optional; numpy array ~ (num_training_samples, num_factors))
            L (optional; numpy array ~ (num_factors,))
            Vt (optional; numpy_array ~ (num_factors, num_hk_genes))

        Returns:
            RemoveUnwantedVariation

        """
        self.center = center
        self.hk_genes = None
        self.means = None
        self.U = None
        self.L = None
        self.Vt = None

    def _is_fit(self):
        """
        Check if the batch effect transformation has been fit.

        Args:
            None

        Returns:
            bool

        """
        return (self.hk_genes is not None) and \
               (self.means is not None) and \
               (self.U is not None) and \
               (self.L is not None) and \
               (self.Vt is not None)

    def _cutoff_svd(self, matrix, variance_cutoff=1, num_components=None):
        """
        Compute the singular value decomposition of a matrix and get rid
        of any singular vectors below a cumulative variance threshold.

        Args:
            matrix (numpy array): the data
            variance_cutoff (float): retains only elements of L that contribute
                to the cumulative fractional variance up to the cutoff.
            num_components (int): the maximum number of components of L to use.
                If None, no additional constraint is applied.

        Returns:
            U, L, Vt where M = U L V^{T}

        """
        U, L, Vt = numpy.linalg.svd(matrix, full_matrices=False)
        # trim eigenvalues close to 0, exploit the fact that L is ordered
        L = L[:(~numpy.isclose(L, 0)).sum()]
        cumul_variance_fracs = numpy.cumsum(L**2) / numpy.sum(L**2)
        max_components = len(L) if num_components is None else num_components
        L_cutoff = min(max_components,
                       1+numpy.searchsorted(cumul_variance_fracs, variance_cutoff))
        return U[:, :L_cutoff], L[:L_cutoff], Vt[:L_cutoff, :]

    def fit(self, data, hk_genes, variance_cutoff=0.9, num_components=None):
        """
        Perform a singular value decomposition of the housekeeping genes to
        fit the transform.

        Suppose that we measure data on the expression of N genes in M samples
        and store these (after CLR transformation) in a matrix Y \in R^{M, N}.
        We consider a linear model Y = X B + W A + noise where
            X \in R^{M, Q} are some unobserved, but biologically interesting, factors
            B \in R^{Q, N} describes how the genes are coupled to the interesting factors
            W \in R^{M, K} are some unobserved and uninteresting factors
            A \in R^{K, N} describes how the genes are coupled to the uninteresting factors

        We assume that there are some housekeeping genes Y_c for which we are
        sure that B_c = 0. That is, the housekeeping genes are not coupled to
        any biologically interesting factors. Therefore, we have Y_c = W A_c + noise.
        Let Y_c = U L V^{T} be the singular value decomposition of Y_c. Then,
        we can estiamte W = U L.  Additionally, A_c = V^{T}.

        Now, if we fix W and assume that X B = 0 for all genes then we can
        estimate A = W^+ Y = (W W^{T})^{-1} W^{T} Y.
        This matrix stores K patterns of variation that are
        usually not biologically interesting.

        Args:
            data (pandas.DataFrame ~ (num_samples, num_genes)): clr transformed
                expression data
            hk_genes (List[str]): list of housekeeping genes
            variance_cutoff (float): the cumulative variance cutoff on SVD
                eigenvalues of Y_c (the variance fraction of the factors).
            num_components (int): the maximum number of components K to use.
                If None, all components are used (up to the variance cutoff).

        Returns:
            None

        """
        self.means = data.mean(axis=0)
        # restrict to available housekeeping genes
        self.hk_genes = [gene for gene in hk_genes if gene in data.columns]
        # center the data along genes
        if self.center:
            housekeeping = data[self.hk_genes] - self.means[self.hk_genes]
        else:
            housekeeping = data[self.hk_genes]
        self.U, self.L, self.Vt = self._cutoff_svd(housekeeping, variance_cutoff,
                                                   num_components)

    def _delta(self, W, data_centered, penalty):
        """
        Compute the corrections for RUV2.

        Args:
            W (numpy array ~ (num_samples, num_factors))
            data_centered (pandas.DataFrame ~ (num_samples, num_genes))
            penalty (float)

        Returns:
            delta (numpy array ~ (num_samples, num_genes))

        """
        penalty_term = penalty * numpy.eye(W.shape[1])
        J = numpy.linalg.inv(penalty_term + numpy.dot(W.T, W))
        return numpy.dot(W, numpy.dot(J, numpy.dot(W.T, data_centered)))

    def transform(self, data, penalty=0):
        """
        Perform the 2-step Remove Unwanted Variation (RUV-2) algorithm.

        The `fit` method estimates the matrix
            A \in R^{K, N} which describes how the genes are coupled to the
            uninteresting factors

        We can estimate the activity of these factors from a new dataset \tilde{Y}
        by using the housekeeping genes on this new dataset and computing
        \tilde{W} = \tilde{Y}_c A_c^{+}.  Since A_c = V^{T} from the SVD,
        the right pseudoinverse A_c^{+} = A_c^{T}.

        Finally, we can subtract \tilde{W} A from the data,
        \tilde{Y} - \tilde{W} A.

        Essentially, we are removing the components of the data that project
        onto the pre-defined axes of uninteresting variation.

        Args:
            data (pandas.DataFrame ~ (num_samples, num_genes)): clr transformed
                expression data
            penalty (float): regularization on the regression step

        Returns:
            batch corrected data (pandas.DataFrame ~ (num_samples, num_genes))

        """
        assert self._is_fit(), "RUV has not been fit!"
        if self.center:
            data_trans = data - self.means
        else:
            data_trans = data
        W = numpy.dot(data_trans[self.hk_genes], self.Vt.T)
        return data - self._delta(W, data_trans, penalty)

    def fit_transform(self, data, hk_genes, penalty=0, variance_cutoff=0.9,
                      num_components=None):
        """
        Perform the 2-step Remove Unwanted Variation (RUV-2) algorithm.

        Args:
            data (pandas.DataFrame ~ (num_samples, num_genes)): clr transformed
                expression data
            hk_genes (List[str]): list of housekeeping genes
            penalty (float): regularization on the regression step
            variance_cutoff (float): the cumulative variance cutoff on SVD
                eigenvalues of Y_c.
            num_components (int): the maximum number of components K to use.
                If None, all components are used (up to the variance cutoff).

        Returns:
            batch corrected data (pandas.DataFrame ~ (num_samples, num_genes))

        """
        self.fit(data, hk_genes, variance_cutoff, num_components)
        return self.transform(data, penalty)

    def save(self, filename, overwrite_existing=False):
        """
        Save the RUV object to filename.

        Args:
            filename (string): absolute path to save file
            overwrite_existing (bool): whether or not to overwrite existing file

        Returns:
            None

        """
        path = Path(filename)
        assert overwrite_existing or not path.exists(), \
            "Must allow overwriting existing files"
        with open(filename, 'wb') as f:
            pickle.dump(self, f)

    @classmethod
    def load(cls, filename):
        """
        Create an RUV from a saved object.

        Args:
            filename (str)

        Returns:
            RemoveUnwantedVaraition

        """
        with open(filename, 'rb') as f:
            return pickle.load(f)
