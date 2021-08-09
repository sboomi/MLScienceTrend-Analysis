import re
from typing import List, Union
import streamlit as st
import pandas as pd
import requests
from pydantic import BaseModel, NoneStr

BASE_URL = "http://api.archives-ouvertes.fr/search/"
FMT_LIST = [
    ("JSON", "json"),
    ("XML", "xml"),
    ("XML-TEI", "xml-tei"),
    ("BibTeX", "bibtex"),
    ("Endnote", "endnote"),
    ("Flux RSS", "rss"),
    ("Flux Atom", "atom"),
    ("CSV", "csv"),
]


class RequestParams(BaseModel):
    collection: NoneStr = ""
    text: NoneStr = "*:*"
    title_t: Union[NoneStr, List[str]] = "title_t:*"
    format: str = "json"
    res_fields: List[str] = []
    sorting_field: str = "docid"
    ascending: bool = False
    rows_per_page: int = 30
    offset: int = 0


def build_url(rp: RequestParams) -> str:
    r_url = BASE_URL + (f"{rp.collection}/" if rp.collection else "")
    r_url += f'q="{rp.text}"'
    r_url += f"&wt={rp.format}"
    r_url += f"fl={','.join(rp.res_fields)}"
    r_url += f"&start={rp.offset}&rows={rp.rows_per_page}"
    r_url += f"&sort={rp.sorting_field} {'asc' if rp.ascending else 'desc'}"
    return r_url


@st.cache
def get_instances():
    url_instance = "https://api.archives-ouvertes.fr/ref/instance"
    r = requests.get(url_instance)
    if r.status_code == 200:
        res = r.json()
    else:
        print(r.status_code)
    data = {k: [] for k in res["response"]["docs"][0].keys()}
    for doc in res["response"]["docs"]:
        for k, v in doc.items():
            data[k].append(v)

    df = pd.DataFrame(data)
    return df


@st.cache
def get_response_params():
    r = requests.get("http://api.archives-ouvertes.fr/search/?q=*:*&wt=jsonl&fl=*&rows=1")
    res = r.json()
    return list(res["response"]["docs"][0].keys())


st.title("HAL archives ouvertes")
st.write(f"The base URL is here {BASE_URL}")

request_params = RequestParams()
r_url = build_url(request_params)

instances = get_instances()
response_fields = get_response_params()

st.write(f"Current request URL: {r_url}")


st.header("Portal")

option = st.selectbox("Select a portal", instances.name)
st.write("You selected:", option)
request_params.collection = instances[instances.name == option].code.values[0]

st.header("Requests")

st.subheader("General request")
text_query = st.text_input("Any general query?", "You can leave blank too")
st.write("Your query is", text_query)
request_params.text = text_query

st.subheader("Token words for the title")
st.markdown("""**Tips**: you can enter regex characters for an extensive research like `?`, `*` or `~{n}`""")
title_query = st.text_input("Enter multiple tokens for your research", "Separate them with a comma")
title_query_tokens = [token.strip() for token in title_query.split(",")]

title_tokens = st.multiselect("Do you want to make a combined research?", title_query_tokens)
request_params.title_t = title_tokens
st.write("Note: we can still use conditionals like AND and OR")

st.subheader("Return format")

fmt = st.radio("Select a return format (note: CSV is recommended)", FMT_LIST, format_func=lambda x: x[0])
st.write("You picked ", fmt[0])
request_params.format = fmt[1]

st.header("Response")

st.subheader("Response fields")

picked_res_fields = st.multiselect("Pick your fields (default: doc_id and label_s)", response_fields)
request_params.res_fields = picked_res_fields

st.subheader("Sort results")
sort_field = st.selectbox("Field to sort with", picked_res_fields)
ascending = st.checkbox("Ascending")

request_params.sorting_field = sort_field
request_params.ascending = ascending

st.header("Number of results")

n_per_page = st.slider("How many rows per page?", 1, 200)
request_params.rows_per_page = n_per_page

start_page = st.number_input("Enter an offset page", min_value=0, value=0)
request_params.offset = start_page

st.header("Final request")

st.markdown(f"Final URL request `{build_url(request_params)}`")

if st.button("Request data"):
    r_url = build_url(request_params)
    r = requests.get(r_url)
    if r.status_code == 200:
        st.write(r.content if request_params.format != "json" else r.json())
    else:
        st.warning(f"Status code: {r.status_code} / URL: {r_url}")
        st.stop()
