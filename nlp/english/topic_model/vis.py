"""
Generate wordcloud and other visualizations for each topic model result.
"""
import argparse
import json
import pandas as pd
from math import ceil
from tqdm import tqdm
from matplotlib import pyplot as plt
from matplotlib.colors import TwoSlopeNorm, LinearSegmentedColormap
from wordcloud import WordCloud
import seaborn as sns
plt.rcParams.update({'font.size': 10})


def read_json(json_file):
    """Read in JSON file with error handler in case it doesn't exist."""
    try:
        with open(json_file, 'r') as f:
            content = json.load(f)
    except FileNotFoundError:
        print(f"Did not find {json_file} in current directory, skipping...")
        content = ''
    return content


def get_param_table(param_dict):
    """View the parameter dictionary as a Pandas DataFrame"""
    params = pd.DataFrame.from_dict(param_dict, orient='index')
    params.columns = ['value']
    params['value'] = params['value'].astype(object)
    return params


def get_top_n_words(topic_dict, n=5):
    """Return a list of top-n words for each topic. This list can
       then be used as an axis label if required.
    """
    top_words = []
    for num, words in topic_dict.items():
        sorted_words = {k: v for k, v in sorted(words.items(),
                                                key=lambda x: x[1],
                                                reverse=True
                                                )}
        words = sorted_words.keys()
        top_n_words = list(words)[:n]
        top_words.append(', '.join(top_n_words))
    return top_words


def construct_outletDF(outlet_avg_dict, topics):
    """Read the topic distribution per outlet into a DataFrame and reorder by importance"""
    outlet_topicsDF = pd.DataFrame.from_dict(outlet_avg_dict, orient='index').transpose()
    outlet_topicsDF['sum'] = outlet_topicsDF[outlet_topicsDF.columns].sum(axis=1)
    # Sort in descending order of the sum of mean values for each topic
    outlet_topicsDF = outlet_topicsDF.sort_values('sum', ascending=False).drop('sum', axis=1)

    # Get a properly ordered list of topics based on prominence for axis labelling
    ordered_topics_dict = {idx: topics['topics'][idx] for idx in outlet_topicsDF.index}
    return outlet_topicsDF, ordered_topics_dict


def construct_gender_df(gender_avg_dict, topics):
    """Read the topic distribution per gender into a DataFrame and reorder by importance"""
    genderDF = pd.DataFrame.from_dict(gender_avg_dict, orient='index').transpose()
    genderDF = genderDF[['female', 'male']]
    genderDF['female_reversed'] = genderDF['female'] * -1.0
    genderDF['sum'] = genderDF['male'] + genderDF['female']
    # Sort in descending order of the sum of mean values for each topic
    genderDF = genderDF.sort_values('sum', ascending=False)
    genderDF['topic'] = [f"t{i}" for i in genderDF.index]

    # Get a properly ordered list of topics based on prominence for axis labelling
    ordered_topics_dict = {idx: topics['topics'][idx] for idx in genderDF.index}
    return genderDF, ordered_topics_dict


def get_outlet_gender_topicDF(data, gender):
    dataDF = pd.DataFrame.from_dict(data[gender], orient='index')
    outlet_gender_topicsDF = pd.json_normalize(dataDF['topic_mean'])
    outlet_gender_topicsDF.index = dataDF.index
    outlet_gender_topicsDF = outlet_gender_topicsDF.sort_index()
    outlet_gender_topicsDF = outlet_gender_topicsDF.transpose()
    return outlet_gender_topicsDF


def plot_wordclouds(topics, colormap="viridis"):
    """Plot each topic's wordclouds in a fixed-tile representation"""
    cloud = WordCloud(background_color='white',
                      width=600,
                      height=400,
                      colormap=colormap,
                      prefer_horizontal=1.0,
                      )

    num_topics = topics['params']['num_topics']
    fig_width = min(ceil(0.6 * num_topics + 6), 20)
    fig_height = min(ceil(0.65 * num_topics), 20)
    fig = plt.figure(figsize=(fig_width, fig_height))

    for idx, word_weights in tqdm(topics['topics'].items()):
        ax = fig.add_subplot((num_topics / 5) + 1, 5, int(idx))
        wordcloud = cloud.generate_from_frequencies(word_weights)
        ax.imshow(wordcloud, interpolation="bilinear")
        ax.set_title('Topic {}'.format(idx))
        ax.set_xticklabels([])
        ax.set_yticklabels([])
        ax.tick_params(length=0)
        ax.xaxis.grid(False)
        ax.yaxis.grid(False)

    plt.tick_params(labelsize=14)
    plt.subplots_adjust(wspace=0.1, hspace=0.1)
    plt.margins(x=0.1, y=0.1)
    st = fig.suptitle("Begin Date: {}  End Date: {}  Articles: {}".format(
        topics['params']['begin_date'],
        topics['params']['end_date'],
        topics['params']['articleCount']),
        y=0.92
    )
    fig.savefig(f"fig-{prefix}-cloud.png", bbox_extra_artists=[st], bbox_inches='tight')


def plot_heatmap(df, topics, ordered_topics_dict, colormap='Greens'):
    """Plot a heat map showing the mean topic distribution per outlet"""
    topic_words = get_top_n_words(ordered_topics_dict)
    num_topics = topics['params']['num_topics']

    fig_width = min(ceil(0.6 * num_topics + 6), 20)
    fig_height = min(ceil(0.65 * num_topics), 20)
    fig = plt.figure(figsize=(fig_width, fig_height))

    sns.set_color_codes("pastel")
    s = sns.heatmap(df, cmap=sns.color_palette(colormap, 49),
                    linewidths=2.0, square=True)
    s.set_xticklabels(s.get_xticklabels(), rotation=-45, ha='left')
    s.set_yticklabels(topic_words, rotation=0, fontsize=12)
    s.set_xlabel("")
    st = fig.suptitle("Start Date: {}  End Date: {}  Articles: {}".format(
        topics['params']['begin_date'],
        topics['params']['end_date'],
        topics['params']['articleCount']),
        y=0.92
    )
    fig.savefig(f"fig-{prefix}-heatmap.png", bbox_extra_artists=[st], bbox_inches='tight')


def plot_divergent_heatmap(df, topics, ordered_topics_dict, colormap):
    """Plot a heat map showing the mean topic distribution per outlet"""
    topic_words = get_top_n_words(ordered_topics_dict)
    num_topics = topics['params']['num_topics']

    fig_width = min(ceil(0.6 * num_topics + 6), 20)
    fig_height = min(ceil(0.65 * num_topics), 20)
    fig = plt.figure(figsize=(fig_width, fig_height))

    sns.set_color_codes("pastel")
    s = sns.heatmap(df, cmap=colormap, norm=TwoSlopeNorm(0),
                    linewidths=2.0, square=True)
    s.set_xticklabels(s.get_xticklabels(), rotation=-45, ha='left')
    s.set_yticklabels(topic_words, rotation=0, fontsize=12)
    s.set_xlabel("")
    st = fig.suptitle("Start Date: {}  End Date: {}  Articles: {}".format(
        topics['params']['begin_date'],
        topics['params']['end_date'],
        topics['params']['articleCount']),
        y=0.92
    )
    fig.savefig(f"fig-{prefix}-divergent-heatmap.png", bbox_extra_artists=[st], bbox_inches='tight')


def plot_gender_hbars(genderDF, topics, ordered_topics_dict):
    """Plot horizontal bars showing the mean topic distribution per dominant source gender"""
    top_val = max(max(genderDF['male']), max(genderDF['female']))
    top_n_words = get_top_n_words(ordered_topics_dict)
    # Initialize the matplotlib figure
    fig, ax = plt.subplots(figsize=(8, 8))

    sns.set(style="whitegrid")

    sns.barplot(data=genderDF[['topic', 'female_reversed']],
                x='female_reversed', y='topic',
                label='Female sources > male sources',
                orient='h',
                color="#af1858",  # rgb(175, 24, 88)
                ci=None)

    sns.barplot(data=genderDF[['topic', 'male']],
                x='male', y='topic',
                label='Male sources > female sources',
                orient='h',
                color="#004d72",  # rgb(0, 77, 114)
                ci=None)

    # Add a legend and informative axis label
    ax.legend(ncol=2, loc="upper center",
              bbox_to_anchor=(0.5, 1.01), frameon=True)
    ax.set(xlim=(-top_val, top_val), ylabel="",
           xlabel="Mean Topic Weight")
    ax.set_yticklabels(top_n_words, rotation=0, fontsize=12)
    ax.xaxis.grid(False)
    # ax.yaxis.grid(True)

    sns.despine(left=True, bottom=True)
    st = fig.suptitle("Begin Date: {}  End Date: {}".format(
        topics['params']['begin_date'],
        topics['params']['end_date']),
        y=0.92
    )
    plt.subplots_adjust(wspace=0.1, hspace=0.1)
    plt.margins(x=0.1, y=0.1)
    fig.savefig(f"fig-{prefix}-hbars.png", bbox_extra_artists=[st], bbox_inches='tight')


def create_male_female_colormap():
    """Custom colormap for male/female colors in GGT"""
    colors = ["#004d72", "#ffffff","#af1858"]
    nodes = [0.0, 0.5, 1.0]
    bwr_map = LinearSegmentedColormap.from_list("custom", list(zip(nodes, colors)))
    return bwr_map


def main(prefix):
    topics = read_json(f"{prefix}-topic.json")

    if topics:
        # Plot wordclouds
        param_table = get_param_table(topics['params'])
        print(param_table)
        plot_wordclouds(topics)

        # Plot outlet mean topic distributions
        outlet_data = read_json(f"{prefix}-outlet.json")
        if outlet_data:
            outlet_topicsDF, ordered_topics_dict = construct_outletDF(outlet_data, topics)
            plot_heatmap(outlet_topicsDF, topics, ordered_topics_dict)

        # Plot gender mean topic distributions
        gender_data = read_json(f"{prefix}-gender.json")
        if gender_data:
            genderDF, ordered_topics_dict = construct_gender_df(gender_data, topics)
            plot_gender_hbars(genderDF, topics, ordered_topics_dict)

        outlet_gender_data = read_json(f"{prefix}-outlet-gender.json")
        if outlet_gender_data:
            bwr_colormap = create_male_female_colormap()
            male_outlet_topics = get_outlet_gender_topicDF(outlet_gender_data, 'male')
            female_outlet_topics = get_outlet_gender_topicDF(outlet_gender_data, 'female')
            # Plot the difference between the male-dominant and female-dominant topics
            diff = female_outlet_topics - male_outlet_topics
            # Calculate sum of all columns to decide sorting order
            diff['net'] = diff[diff.columns].sum(axis=1)
            diff = diff.sort_values('net', ascending=False).drop('net', axis=1)
            # Get a properly ordered list of topics based on prominence for axis labelling
            ordered_topics_dict = {idx: topics['topics'][idx] for idx in diff.index}
            plot_divergent_heatmap(diff, topics, ordered_topics_dict, colormap=bwr_colormap)

    else:
        print("Skipping. Did not find valid topic parameters and words/weights.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--file_prefix', '-f', nargs='+', type=str,
                        required=True, help="File prefix of output JSON file")
    args = parser.parse_args()
    file_prefix = args.file_prefix

    for prefix in file_prefix:
        main(prefix)



