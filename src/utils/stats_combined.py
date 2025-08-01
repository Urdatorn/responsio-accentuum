from src.stats import accentual_responsion_metric_corpus, accentual_responsion_metric_play
from src.stats_barys import barys_oxys_metric_corpus, barys_oxys_metric_play
from src.stats_comp import compatibility_corpus, compatibility_play, compatibility_ratios_to_stats

def all_three_metrics_corpus(folder_path):
    '''
    Picks out the three most important metrics for the whole corpus:
    - Acute-circumflex accentual responsion (not grave)
    - Barys-only responsion (not oxys) 
    - Compatibility of melodic contour 
    '''

    accentual_responsion_metric = accentual_responsion_metric_corpus(folder_path)
    acute_circumflex = accentual_responsion_metric['acute_circumflex']

    barys_responsion_metric = barys_oxys_metric_corpus(folder_path)
    barys_only = barys_responsion_metric['barys_metric']

    compatibility_metric = compatibility_ratios_to_stats(compatibility_corpus(folder_path))

    return {
        'acute_circumflex_responsion': acute_circumflex,
        'barys_responsion': barys_only,
        'contour_compatibility': compatibility_metric
    }

def all_three_metrics_play(abbreviation):
    xml_path = f'data/compiled/responsion_{abbreviation}_compiled.xml'

    accentual_responsion_metric = accentual_responsion_metric_play(xml_path)
    acute_circumflex = accentual_responsion_metric['acute_circumflex']

    barys_responsion_metric = barys_oxys_metric_play(abbreviation)
    barys_only = barys_responsion_metric['barys_metric']

    compatibility_metric = compatibility_ratios_to_stats(compatibility_play(xml_path))

    return {
        'acute_circumflex_responsion': acute_circumflex,
        'barys_responsion': barys_only,
        'contour_compatibility': compatibility_metric
    }
