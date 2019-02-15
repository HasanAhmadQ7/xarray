import functools

from ..core.alignment import broadcast
from .facetgrid import _easy_facetgrid
from .utils import (
    _add_colorbar, _is_numeric, _process_cmap_cbar_kwargs, get_axis,
    label_from_attrs)


def _infer_meta_data(ds, x, y, hue, hue_style, add_guide):
    dvars = set(ds.variables.keys())
    error_msg = (' must be one of ({0:s})'
                 .format(', '.join(dvars)))

    if x not in dvars:
        raise ValueError('x' + error_msg)

    if y not in dvars:
        raise ValueError('y' + error_msg)

    if hue is not None and hue not in dvars:
        raise ValueError('hue' + error_msg)

    if hue:
        hue_is_numeric = _is_numeric(ds[hue].values)

        if hue_style is None:
            hue_style = 'continuous' if hue_is_numeric else 'discrete'

        if not hue_is_numeric and (hue_style == 'continuous'):
            raise ValueError('Cannot create a colorbar for a non numeric'
                             ' coordinate: ' + hue)

        if add_guide is None:
            add_colorbar = True if hue_style == 'continuous' else False
            add_legend = True if hue_style == 'discrete' else False

    else:
        if add_guide is True:
            raise ValueError('Cannot set add_guide when hue is None.')
        add_legend = False
        add_colorbar = False

    if hue_style is not None and hue_style not in ['discrete', 'continuous']:
        raise ValueError('hue_style must be either None, \'discrete\' '
                         'or \'continuous\'.')

    if hue:
        hue_label = label_from_attrs(ds[hue])
        hue_values = ds[hue].values
    else:
        hue_label = None
        hue_values = None

    return {'add_colorbar': add_colorbar,
            'add_legend': add_legend,
            'hue_label': hue_label,
            'hue_style': hue_style,
            'xlabel': label_from_attrs(ds[x]),
            'ylabel': label_from_attrs(ds[y]),
            'hue_values': hue_values}


def _infer_scatter_data(ds, x, y, hue):

    broadcast_keys = ['x', 'y']
    to_broadcast = [ds[x], ds[y]]
    if hue:
        to_broadcast.append(ds[hue])
        broadcast_keys.append('hue')
    if scatter_size:
        to_broadcast.append(ds[scatter_size])
        broadcast_keys.append('size')

    broadcasted = dict(zip(broadcast_keys, broadcast(*to_broadcast)))

    data = {'x': broadcasted['x'].values.flatten(),
            'y': broadcasted['y'].values.flatten(),
            'color': None,
            'sizes': None}

    if hue:
        data['color'] = broadcasted['hue'].values.flatten()

    if scatter_size:
        ss = (broadcast(ds[scatter_size], xx)[0]
              .values.flatten())

        size_mapping = _parse_size(ss, size_norm)

        if _is_numeric(ss):
            data['sizes'] = np.array(size_mapping.values())[
                np.digitize(ss, np.array(size_mapping.keys()))]
        else:
            data['sizes'] = np.array([size_mapping.get(s0) for s0 in ss])

    return data


class _Dataset_PlotMethods(object):
    """
    Enables use of xarray.plot functions as attributes on a Dataset.
    For example, Dataset.plot.scatter
    """

    def __init__(self, dataset):
        self._ds = dataset

    def __call__(self, *args, **kwargs):
        raise ValueError('Dataset.plot cannot be called directly. Use '
                         'an explicit plot method, e.g. ds.plot.scatter(...)')


def _dsplot(plotfunc):
    commondoc = """
    Parameters
    ----------

    ds : Dataset
    x, y : string
        Variable names for x, y axis.
    hue: str, optional
        Variable by which to color scattered points
    hue_style: str, optional
        Hue style. Can be either 'discrete' or 'continuous'.
    add_guide: bool, optional
        Add a guide that depends on hue_style
            - for "discrete", build a legend.
              This is the default for non-numeric `hue` variables.
            - for "continuous",  build a colorbar
    row : string, optional
        If passed, make row faceted plots on this dimension name
    col : string, optional
        If passed, make column faceted plots on this dimension name
    col_wrap : integer, optional
        Use together with ``col`` to wrap faceted plots
    ax : matplotlib axes, optional
        If None, uses the current axis. Not applicable when using facets.
    subplot_kws : dict, optional
        Dictionary of keyword arguments for matplotlib subplots. Only applies
        to FacetGrid plotting.
    aspect : scalar, optional
        Aspect ratio of plot, so that ``aspect * size`` gives the width in
        inches. Only used if a ``size`` is provided.
    size : scalar, optional
        If provided, create a new figure for the plot with the given size.
        Height (in inches) of each plot. See also: ``aspect``.
    norm : ``matplotlib.colors.Normalize`` instance, optional
        If the ``norm`` has vmin or vmax specified, the corresponding kwarg
        must be None.
    vmin, vmax : floats, optional
        Values to anchor the colormap, otherwise they are inferred from the
        data and other keyword arguments. When a diverging dataset is inferred,
        setting one of these values will fix the other by symmetry around
        ``center``. Setting both values prevents use of a diverging colormap.
        If discrete levels are provided as an explicit list, both of these
        values are ignored.
    cmap : matplotlib colormap name or object, optional
        The mapping from data values to color space. If not provided, this
        will be either be ``viridis`` (if the function infers a sequential
        dataset) or ``RdBu_r`` (if the function infers a diverging dataset).
        When `Seaborn` is installed, ``cmap`` may also be a `seaborn`
        color palette. If ``cmap`` is seaborn color palette and the plot type
        is not ``contour`` or ``contourf``, ``levels`` must also be specified.
    colors : discrete colors to plot, optional
        A single color or a list of colors. If the plot type is not ``contour``
        or ``contourf``, the ``levels`` argument is required.
    center : float, optional
        The value at which to center the colormap. Passing this value implies
        use of a diverging colormap. Setting it to ``False`` prevents use of a
        diverging colormap.
    robust : bool, optional
        If True and ``vmin`` or ``vmax`` are absent, the colormap range is
        computed with 2nd and 98th percentiles instead of the extreme values.
    extend : {'neither', 'both', 'min', 'max'}, optional
        How to draw arrows extending the colorbar beyond its limits. If not
        provided, extend is inferred from vmin, vmax and the data limits.
    levels : int or list-like object, optional
        Split the colormap (cmap) into discrete color intervals. If an integer
        is provided, "nice" levels are chosen based on the data range: this can
        imply that the final number of levels is not exactly the expected one.
        Setting ``vmin`` and/or ``vmax`` with ``levels=N`` is equivalent to
        setting ``levels=np.linspace(vmin, vmax, N)``.
    **kwargs : optional
        Additional keyword arguments to matplotlib
    """

    # Build on the original docstring
    plotfunc.__doc__ = '%s\n%s' % (plotfunc.__doc__, commondoc)

    @functools.wraps(plotfunc)
    def newplotfunc(ds, x=None, y=None, hue=None, hue_style=None,
                    col=None, row=None, ax=None, figsize=None, size=None,
                    col_wrap=None, sharex=True, sharey=True, aspect=None,
                    subplot_kws=None, add_guide=None, cbar_kwargs=None,
                    cbar_ax=None, vmin=None, vmax=None,
                    norm=None, infer_intervals=None, center=None, levels=None,
                    robust=None, colors=None, extend=None, cmap=None,
                    **kwargs):

        _is_facetgrid = kwargs.pop('_is_facetgrid', False)
        if _is_facetgrid:  # facetgrid call
            meta_data = kwargs.pop('meta_data')
        else:
            meta_data = _infer_meta_data(ds, x, y, hue, hue_style, add_guide)

        hue_style = meta_data['hue_style']

        # handle facetgrids first
        if col or row:
            allargs = locals().copy()
            allargs['plotfunc'] = globals()[plotfunc.__name__]
            allargs['data'] = ds
            # TODO dcherian: why do I need to remove kwargs?
            for arg in ['meta_data', 'kwargs', 'ds']:
                del allargs[arg]

            return _easy_facetgrid(kind='dataset', **allargs)

        figsize = kwargs.pop('figsize', None)
        ax = get_axis(figsize, size, aspect, ax)

        if hue_style == 'continuous' and hue is not None:
            if _is_facetgrid:
                cbar_kwargs = meta_data['cbar_kwargs']
                cmap_params = meta_data['cmap_params']
            else:
                cmap_params, cbar_kwargs = _process_cmap_cbar_kwargs(
                    plotfunc, locals(), ds[hue].values)

            # subset that can be passed to scatter, hist2d
            cmap_params_subset = dict(
                (vv, cmap_params[vv])
                for vv in ['vmin', 'vmax', 'norm', 'cmap'])

        else:
            cmap_params_subset = {}

        primitive = plotfunc(ds=ds, x=x, y=y, hue=hue, hue_style=hue_style,
                             ax=ax, cmap_params=cmap_params_subset, **kwargs)

        if _is_facetgrid:  # if this was called from Facetgrid.map_dataset,
            return primitive        # finish here. Else, make labels

        if meta_data.get('xlabel', None):
            ax.set_xlabel(meta_data.get('xlabel'))
        if meta_data.get('ylabel', None):
            ax.set_ylabel(meta_data.get('ylabel'))

        if meta_data['add_legend']:
            ax.legend(handles=primitive,
                      labels=list(meta_data['hue_values']),
                      title=meta_data.get('hue_label', None))
        if meta_data['add_colorbar']:
            cbar_kwargs = {} if cbar_kwargs is None else cbar_kwargs
            if 'label' not in cbar_kwargs:
                cbar_kwargs['label'] = meta_data.get('hue_label', None)
            _add_colorbar(primitive, ax, cbar_ax, cbar_kwargs, cmap_params)

        return primitive

    @functools.wraps(newplotfunc)
    def plotmethod(_PlotMethods_obj, x=None, y=None, hue=None,
                   hue_style=None, col=None, row=None, ax=None,
                   figsize=None,
                   col_wrap=None, sharex=True, sharey=True, aspect=None,
                   size=None, subplot_kws=None, add_guide=None,
                   cbar_kwargs=None, cbar_ax=None, vmin=None, vmax=None,
                   norm=None, infer_intervals=None, center=None, levels=None,
                   robust=None, colors=None, extend=None, cmap=None,
                   **kwargs):
        """
        The method should have the same signature as the function.

        This just makes the method work on Plotmethods objects,
        and passes all the other arguments straight through.
        """
        allargs = locals()
        allargs['ds'] = _PlotMethods_obj._ds
        allargs.update(kwargs)
        for arg in ['_PlotMethods_obj', 'newplotfunc', 'kwargs']:
            del allargs[arg]
        return newplotfunc(**allargs)

    # Add to class _PlotMethods
    setattr(_Dataset_PlotMethods, plotmethod.__name__, plotmethod)

    return newplotfunc


@_dsplot
def scatter(ds, x, y, ax, **kwargs):
    """ Scatter Dataset data variables against each other. """

    if 'add_colorbar' in kwargs or 'add_legend' in kwargs:
        raise ValueError('Dataset.plot.scatter does not accept '
                         + '\'add_colorbar\' or \'add_legend\'. '
                         + 'Use \'add_guide\' instead.')

    cmap_params = kwargs.pop('cmap_params')
    hue = kwargs.pop('hue')
    hue_style = kwargs.pop('hue_style')

    if hue_style == 'discrete':
        primitive = []
        for label, grp in ds.groupby(ds[hue]):
            data = _infer_scatter_data(grp, x, y, hue=None)
            primitive.append(ax.scatter(data['x'], data['y'], label=label,
                                        **kwargs))

    elif hue is None or hue_style == 'continuous':
        data = _infer_scatter_data(ds, x, y, hue)

        primitive = ax.scatter(data['x'], data['y'], c=data['color'],
                               **cmap_params, **kwargs)

    return primitive