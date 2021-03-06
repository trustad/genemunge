# Documentation for Describe (describe.py)

## class Describer
A descriptor for genes.<br />Includes statistics on gene expression in healthy tissue from GTEx.<br /><br />Attributes:<br />    __stats__ (List[str]): a class attribute holding statistic names.<br />    get_ensembl (callable): an instance of convert.IDConverter.convert<br />        to get the Ensembl ID.<br />    get_name (callable): an instance of convert.IDConverter.convert<br />        to get the gene name.<br />    get_symbol (callable): an instance of convert.IDConverter.convert<br />        to get the gene symbol.<br />    searcher (Searcher): an instance of search.Searcher to get gene info.<br />    tissue_stats (dict{str: DataFrame}): per-tissue statistics from GTEx.
### \_\_init\_\_
```py

def __init__(self, identifier='symbol', load_tissue_data=True)

```



Create an object to grab the information that describes a gene.<br /><br />Args:<br />&nbsp;&nbsp;&nbsp;&nbsp;identifier (optional; str): the type of gene identifier you will use<br />&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;e.g., 'symbol', 'ensembl_gene_id'<br /><br />Returns:<br />&nbsp;&nbsp;&nbsp;&nbsp;Describer


### close
```py

def close(self)

```



Close the tissue stats HDF5 store if it is open.<br /><br />Args:<br />&nbsp;&nbsp;&nbsp;&nbsp;None<br /><br />Returns:<br />&nbsp;&nbsp;&nbsp;&nbsp;None


### get\_gene\_info
```py

def get_gene_info(self, identifier)

```



Get some information about a gene such as:<br />&nbsp;&nbsp;&nbsp;&nbsp;ensemble_gene_id<br />&nbsp;&nbsp;&nbsp;&nbsp;gene symbol<br />&nbsp;&nbsp;&nbsp;&nbsp;name<br />&nbsp;&nbsp;&nbsp;&nbsp;associated categories in the Gene Ontology<br /><br />Args:<br />&nbsp;&nbsp;&nbsp;&nbsp;identifier (str)<br /><br />Returns:<br />&nbsp;&nbsp;&nbsp;&nbsp;None


### get\_tissue\_expression
```py

def get_tissue_expression(self, identifier)

```



Get statistics describing the expression of a gene across tissues<br />in healthy people (from GTEx).<br /><br />Args:<br />&nbsp;&nbsp;&nbsp;&nbsp;identifier (str)<br /><br />Returns:<br />&nbsp;&nbsp;&nbsp;&nbsp;pandas.DataFrame


### plot\_tissue\_expression
```py

def plot_tissue_expression(self, identifier, sortby=None, show=True, filename=None)

```



Plot the expression of a gene across tissues in health people<br />(from GTEx).<br /><br />Args:<br />&nbsp;&nbsp;&nbsp;&nbsp;identifier (str)<br />&nbsp;&nbsp;&nbsp;&nbsp;sortby (optional; str): 'median', 'mean', 'std', 'lower_quartile'<br />&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;or 'upper_quartile'. if None, then tissues are alphabetical<br />&nbsp;&nbsp;&nbsp;&nbsp;filename (optional; str)<br /><br />Returns:<br />&nbsp;&nbsp;&nbsp;&nbsp;None



