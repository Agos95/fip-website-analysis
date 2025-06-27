import json
import os
from argparse import ArgumentParser
from dataclasses import asdict, dataclass, field
from random import uniform as urand
from time import sleep

import httpx
from bs4 import BeautifulSoup
from tqdm import tqdm

_BASE_URL = "https://fip.it/risultati/"
_CONFIG_FILE = "scrape/campionati_regionali.json"
_PARSER = "lxml"
_HTML_OUT_FOLDER = "scraped_website"

client = httpx.Client(base_url=_BASE_URL)


@dataclass
class ParamLabelMapping:
    comitato_codice: list[dict[str, str]] = field(default_factory=list)
    sesso: list[dict[str, str]] = field(default_factory=list)
    codice_campionato: list[dict[str, str]] = field(default_factory=list)
    codice_fase: list[dict[str, str]] = field(default_factory=list)
    codice_girone: list[dict[str, str]] = field(default_factory=list)


def _get_soup(client: httpx.Client, params: dict) -> BeautifulSoup:
    sleep(urand(0, 3))
    response = client.get("", params=params)
    return BeautifulSoup(response.text, _PARSER)


def _get_comitato_codice(soup: BeautifulSoup) -> dict[str, str]:
    comitato_codice = {}
    for opt in soup.find(id="province").find("select").find_all("option"):
        comitato_codice[opt.text.strip()] = opt.attrs["value"]
    return comitato_codice


def _get_sesso(soup: BeautifulSoup) -> dict[str, str]:
    sesso = {}
    for opt in soup.find(id="sesso-wrapper").find("select").find_all("option"):
        sesso[opt.text.strip()] = opt.attrs["value"]


def _get_codice_campionato(soup: BeautifulSoup) -> dict[str, str]:
    codice_campionato = {}
    for opt in soup.find(id="campionati").find("select").find_all("option"):
        codice_campionato[opt.text.strip()] = opt.attrs["value"]
    return codice_campionato


def _get_codice_fase(soup: BeautifulSoup) -> dict[str, str]:
    codice_fase = {}
    for opt in soup.find(id="fasi").find("select").find_all("option"):
        codice_fase[opt.text.strip()] = opt.attrs["value"]
    return codice_fase


def _get_codice_girone(soup: BeautifulSoup) -> dict[str, str]:
    codice_girone = {}
    for opt in soup.find(id="gironi").find("select").find_all("option"):
        codice_girone[opt.text.strip()] = opt.attrs["value"]
    return codice_girone


def _get_links(soup: BeautifulSoup):
    links = []
    for day in soup.find("div", attrs={"class": "results-calendar"}).find_all(
        "div", attrs={"class": "results-calendar__days__group"}
    ):
        for a in day.find("div", attrs={"class": "values"}).find_all("a"):
            links.append(a.get("href"))
    return links


def get_all_links(url: str) -> tuple[list[str], ParamLabelMapping]:
    global client

    mapping = ParamLabelMapping()
    links = []

    params = dict(httpx.URL(url).params)
    soup = _get_soup(client, params)
    comitato_codice = _get_comitato_codice(soup)

    for comitato_label, comitato in tqdm(comitato_codice.items(), leave=False):
        mapping.comitato_codice.append({comitato: comitato_label})
        params["comitato_codice"] = comitato
        soup = _get_soup(client, params)
        sesso = _get_sesso(soup)
        if sesso is None:
            continue
        for sex_label, sex in tqdm(sesso.items(), leave=False):
            mapping.sesso.append({sex: sex_label})
            params["sesso"] = sex
            soup = _get_soup(client, params)
            codice_campionato = _get_codice_campionato(soup)
            for campionato_label, campionato in tqdm(
                codice_campionato.items(), leave=False
            ):
                mapping.codice_campionato.append({campionato, campionato_label})
                params["codice_campionato"] = campionato
                soup = _get_soup(client, params)
                codice_fase = _get_codice_fase(soup)
                for fase_label, fase in tqdm(codice_fase.items(), leave=False):
                    mapping.codice_fase.append({fase: fase_label})
                    params["codice_fase"] = fase
                    soup = _get_soup(client, params)
                    codice_girone = _get_codice_girone(soup)
                    for girone_label, girone in tqdm(
                        codice_girone.items(), leave=False
                    ):
                        mapping.codice_girone.append({girone: girone_label})
                        params["codice_girone"] = girone
                        soup = _get_soup(client, params)
                        links += _get_links(soup)

    return links, mapping


def cli_args():
    parser = ArgumentParser()
    parser.add_argument("-r", "--region", type=str, default=None, help="Region")

    return vars(parser.parse_args())


def main(args):
    global client

    config: list[dict[str, str]]
    with open(_CONFIG_FILE, "r") as f:
        config = json.load(f)

    if args["region"] is not None:
        config = [c for c in config if c["region"] == args["region"]]

    for c in tqdm(config):
        links, mapping = get_all_links(c["url"])
        region_folder = os.path.join(
            _HTML_OUT_FOLDER,
            *str(httpx.URL(c["url"]).params).split("&")[:2],
        )
        os.makedirs(region_folder, exist_ok=True)
        with open(os.path.join(region_folder, "mappings.json"), "w") as f:
            json.dump(asdict(mapping), f)
        for link in tqdm(links):
            urand(0, 1)
            response = client.get(link)
            folder = os.path.join(
                _HTML_OUT_FOLDER,
                *str(httpx.URL(link).params).split("&"),
            )
            os.makedirs(folder)
            with open(os.path.join(folder, "index.html"), "w"):
                f.write(BeautifulSoup(response.text, _PARSER).prettify())


if __name__ == "__main__":
    args = cli_args()
    main(args)
