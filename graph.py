import pandas as pd
from pyvis.network import Network

data = pd.read_excel("psb_literary_references.xlsx")

data = data.dropna(subset=["Song / Work"])


from collections import Counter

author_counter = Counter()
for _, row in data.iterrows():
    authors_raw = str(row["Referenced Author(s)"])
    if authors_raw != "nan":
        for a in authors_raw.split("/"):
            a = a.strip()
            if a:
                author_counter[a] += 1



net = Network(
    height="800px",
    width="100%",
    bgcolor="#111111",
    font_color="white",
    directed=False
)


net.set_options("""
{
    "nodes": {
        "font": {
            "size": 16,
            "color": "#ffffff",
            "face": "arial",
            "strokeWidth": 2,
            "strokeColor": "#111111"
        },
        "scaling": {
            "label": {
                "enabled": false
            }
        }
    },

    "physics": {
        "enabled": true,
        "solver": "forceAtlas2Based",
        "forceAtlas2Based": {
            "theta": 0.5,
            "gravitationalConstant": -50,
            "centralGravity": 0.01,
            "springLength": 100,
            "springConstant": 0.08,
            "damping": 0.4,
            "avoidOverlap": 0
        },
        "stabilization": {
            "enabled": true,
            "iterations": 1000
        }
    },

    "interaction": {
        "dragNodes": true,
        "hideEdgesOnDrag": false,
        "hideNodesOnDrag": false
    },

    "edges": {
        "smooth": {
            "enabled": true,
            "type": "dynamic"
        }
    },

    "configure": {
        "enabled": true,
        "filter": "physics"
    }
}
""")



from itertools import zip_longest

for _, row in data.iterrows():

    song = str(row["Song / Work"])
    authors = str(row["Referenced Author(s)"])
    work = str(row["Referenced Work / Year"])
    note = str(row["Note (paraphrased)"])




    net.add_node(
        song,
        label=song,
        title=f"""
        <b>Song / Work</b><br>
        {song}<br><br>

        <b>Note</b><br>
        {note}
        """,
        color="#FF3863",
        size=60
    )




    author_list = [a.strip() for a in authors.split("/") if a.strip()] if authors != "nan" else []
    work_list = [w.strip() for w in work.split("/") if w.strip()] if work != "nan" else []

   
    for author, matched_work in zip_longest(author_list, work_list, fillvalue=None):

        if author is None:
        
            if matched_work:
                work_id = "work_" + matched_work
                net.add_node(
                    work_id,
                    label=matched_work,
                    title=f"""
                    <b>Referenced Work / Year</b><br>
                    {matched_work}
                    """,
                    color="#1BE2A7",
                    size=20
                )
                net.add_edge(song, work_id)
            continue

        author_id = "author_" + author

        node_size = 30 + author_counter[author] * 3

        net.add_node(
            author_id,
            label=author,
            title=f"""
            <b>Referenced Author</b><br>
            {author}<br>
            Встречается в {author_counter[author]} песнях
            """,
            color="#1E71FF",
            size=node_size
        )

        net.add_edge(
            song,
            author_id
        )

        if matched_work:

            work_id = "work_" + matched_work

            net.add_node(
                work_id,
                label=matched_work,
                title=f"""
                <b>Referenced Work / Year</b><br>
                {matched_work}
                """,
                color="#1F9D75",
                size=10
            )

            net.add_edge(
                author_id,
                work_id
            )


net.write_html(
    "graph.html",
    notebook=False,
    open_browser=False
)



with open("graph.html", "r", encoding="utf-8") as file:
    html = file.read()


custom_css = """
<style>


#mynetwork {
    position: relative !important;
}


#graph-legend {
    position: absolute !important;
    top: 15px !important;
    right: 15px !important;
    background: rgba(30, 30, 30, 0.96) !important;
    color: white !important;
    padding: 14px 18px !important;
    border-radius: 8px !important;
    font-family: Arial, sans-serif !important;
    font-size: 14px !important;
    z-index: 9999 !important;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5) !important;
    line-height: 1.6 !important;
}

#graph-legend .legend-title {
    font-weight: bold;
    margin-bottom: 8px;
    font-size: 15px;
    border-bottom: 1px solid rgba(255,255,255,0.2);
    padding-bottom: 6px;
}

#graph-legend .legend-item {
    display: flex;
    align-items: center;
    margin-bottom: 6px;
    white-space: nowrap;
}

#graph-legend .legend-dot {
    width: 14px;
    height: 14px;
    border-radius: 50%;
    display: inline-block;
    margin-right: 10px;
    flex-shrink: 0;
    border: 1px solid rgba(255,255,255,0.3);
}

</style>
"""


html = html.replace(
    "</head>",
    custom_css + "\n</head>"
)



legend_html = """
<div id="graph-legend">
    <div class="legend-title">Легенда</div>
    <div class="legend-item"><span class="legend-dot" style="background:#FF3863"></span>Song / Work</div>
    <div class="legend-item"><span class="legend-dot" style="background:#F5A623"></span>Author</div>
    <div class="legend-item"><span class="legend-dot" style="background:#1BE2A7"></span>Literary Work</div>
</div>
"""

html = html.replace(
    '<div class="card" style="width: 100%">',
    '<div class="card" style="width: 100%; position: relative;">' + legend_html
)


html = html.replace(
    '<div id="mynetwork" class="card-body"></div>\n        </div>',
    '<div id="mynetwork" class="card-body"></div>\n        </div>\n\n        <div id="config-panel"></div>'
)

html = html.replace(
    '"configure": {"enabled": true, "filter": "physics"}',
    '"configure": {"enabled": true, "filter": "physics", '
    '"container": document.getElementById(\'config-panel\')}'
)



with open("graph.html", "w", encoding="utf-8") as file:
    file.write(html)