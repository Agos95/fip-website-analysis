import itertools
import json
import os
from argparse import ArgumentParser
from dataclasses import asdict, dataclass, field
from random import uniform as urand
from time import sleep

import httpx
from bs4 import BeautifulSoup
from loguru import logger
from tqdm import tqdm

_BASE_URL = "https://fip.it/risultati/"
_CONFIG_FILE = "scrape/campionati_regionali.json"
_PARSER = "lxml"
_HTML_OUT_FOLDER = "scraped_website"

_SLEEP = 1

_URL_PARAMS = [
    ["group", "regione_codice"],
    ["comitato_codice"],
    ["sesso"],
    ["codice_campionato"],
    ["codice_fase"],
    ["codice_girone"],
]

client = httpx.Client(base_url=_BASE_URL)
logger.remove()
logger.add(lambda msg: tqdm.write(msg, end=""), level="INFO", colorize=True)


@dataclass
class ParamLabelMapping:
    comitato_codice: list[dict[str, str]] = field(default_factory=list)
    sesso: list[dict[str, str]] = field(default_factory=list)
    codice_campionato: list[dict[str, str]] = field(default_factory=list)
    codice_fase: list[dict[str, str]] = field(default_factory=list)
    codice_girone: list[dict[str, str]] = field(default_factory=list)


def _get_soup(client: httpx.Client, params: dict) -> tuple[BeautifulSoup, httpx.URL]:
    while True:
        try:
            response = client.get("", params=params)
            break
        except Exception:
            sleep(urand(0, _SLEEP))
            continue
    logger.debug(f"Got response from url: {response.url}")
    return BeautifulSoup(response.text, _PARSER), response.url


def _get_comitato_codice(soup: BeautifulSoup) -> dict[str, str]:
    comitato_codice = {}
    try:
        for opt in soup.find(id="province").find("select").find_all("option"):
            comitato_codice[opt.text.strip()] = opt.attrs["value"]
    except Exception as e:
        logger.error(f"Failed to get 'comitato_codice': {e}")
    return comitato_codice


def _get_sesso(soup: BeautifulSoup) -> dict[str, str]:
    sesso = {}
    try:
        for opt in soup.find(id="sesso-wrapper").find("select").find_all("option"):
            sesso[opt.text.strip()] = opt.attrs["value"]
    except Exception as e:
        logger.error(f"Failed to get 'sesso': {e}")
    return sesso


def _get_codice_campionato(soup: BeautifulSoup) -> dict[str, str]:
    codice_campionato = {}
    try:
        for opt in soup.find(id="campionati").find("select").find_all("option"):
            codice_campionato[opt.text.strip()] = opt.attrs["value"]
    except Exception as e:
        logger.error(f"Failed to get 'codice_campioanto': {e}")
    return codice_campionato


def _get_codice_fase(soup: BeautifulSoup) -> dict[str, str]:
    codice_fase = {}
    try:
        for opt in soup.find(id="fasi").find("select").find_all("option"):
            codice_fase[opt.text.strip()] = opt.attrs["value"]
    except Exception as e:
        logger.error(f"Failed to get 'codice_fase': {e}")
    return codice_fase


def _get_codice_girone(soup: BeautifulSoup) -> dict[str, str]:
    codice_girone = {}
    try:
        for opt in soup.find(id="gironi").find("select").find_all("option"):
            codice_girone[opt.text.strip()] = opt.attrs["value"]
    except Exception as e:
        logger.error(f"Failed to get 'codice_girone': {e}")
    return codice_girone


def _get_links(soup: BeautifulSoup) -> list[str]:
    links = []
    for day in soup.find("div", attrs={"class": "results-calendar"}).find_all(
        "div", attrs={"class": "results-calendar__days__group"}
    ):
        for a in day.find("div", attrs={"class": "values"}).find_all("a"):
            links.append(a.get("href"))
    return links


def _get_params(params: dict, lvl=0):
    return {
        k: v
        for k, v in params.items()
        if k in itertools.chain.from_iterable(_URL_PARAMS[:lvl])
    }


def get_all_links(url: str) -> tuple[list[str], ParamLabelMapping]:
    global client

    mapping = ParamLabelMapping()
    links = []

    params = dict(httpx.URL(url).params)
    soup, _ = _get_soup(client, params)
    comitato_codice = _get_comitato_codice(soup)

    for comitato_label, comitato in tqdm(
        comitato_codice.items(), leave=False, desc="Comitato"
    ):
        logger.info(f"Processing comitato '{comitato_label}'")
        mapping.comitato_codice.append({comitato: comitato_label})
        params = _get_params(params, 1)
        params["comitato_codice"] = comitato
        logger.debug(f"comitato_label: {json.dumps(params)}")
        soup, _ = _get_soup(client, params)
        sesso = _get_sesso(soup)
        if not sesso:
            continue
        for sex_label, sex in tqdm(sesso.items(), leave=False, desc="Sesso"):
            mapping.sesso.append({sex: sex_label})
            params = _get_params(params, 2)
            params["sesso"] = sex
            logger.debug(f"sex_label: {json.dumps(params)}")
            soup, _ = _get_soup(client, params)
            codice_campionato = _get_codice_campionato(soup)
            if not codice_campionato:
                continue
            for campionato_label, campionato in tqdm(
                codice_campionato.items(), leave=False, desc="Campionato"
            ):
                mapping.codice_campionato.append({campionato: campionato_label})
                params = _get_params(params, 3)
                params["codice_campionato"] = campionato
                logger.debug(f"codice_campionato: {json.dumps(params)}")
                soup, _ = _get_soup(client, params)
                codice_fase = _get_codice_fase(soup)
                if not codice_fase:
                    continue
                for fase_label, fase in tqdm(
                    codice_fase.items(), leave=False, desc="Fase"
                ):
                    mapping.codice_fase.append({fase: fase_label})
                    params = _get_params(params, 4)
                    params["codice_fase"] = fase
                    logger.debug(f"codice_fase: {json.dumps(params)}")
                    soup, _ = _get_soup(client, params)
                    codice_girone = _get_codice_girone(soup)
                    if not codice_girone:
                        continue
                    for girone_label, girone in tqdm(
                        codice_girone.items(), leave=False, desc="Girone"
                    ):
                        mapping.codice_girone.append({girone: girone_label})
                        params = _get_params(params, 5)
                        params["codice_girone"] = girone
                        logger.debug(f"codice_girone: {json.dumps(params)}")
                        soup, href = _get_soup(client, params)
                        try:
                            links += _get_links(soup)
                        except Exception:
                            links += [str(href)]

    return links, mapping


def cli_args():
    parser = ArgumentParser()
    parser.add_argument("-r", "--region", type=str, default=None, help="Region")
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Just get the links, do not actually download the webpages",
    )
    parser.add_argument(
        "--only-download",
        action="store_true",
        help="Only download webpages from the saved list",
    )

    return vars(parser.parse_args())


def main(args):
    global client

    config: list[dict[str, str]]
    with open(_CONFIG_FILE, "r") as f:
        config = json.load(f)

    if args["region"] is not None:
        config = [c for c in config if c["region"] == args["region"]]

    for c in config:
        region_folder = os.path.join(
            _HTML_OUT_FOLDER,
            *str(httpx.URL(c["url"]).params).split("&")[:2],
        )
        if not args["only_download"]:
            logger.info(f"Processing region '{c['region']}'")
            links, mapping = get_all_links(c["url"])
            os.makedirs(region_folder, exist_ok=True)
            with open(os.path.join(region_folder, "mappings.json"), "w") as f:
                json.dump(asdict(mapping), f, indent=2)
            with open(os.path.join(region_folder, "links.json"), "w") as f:
                json.dump(links, f, indent=2)

        if not args["no_download"] or args["only_download"]:
            try:
                with open(os.path.join(region_folder, "links.json"), "r") as f:
                    links = json.load(f)
            except Exception as e:
                logger.error(
                    f"Cannot find {os.path.join(region_folder, 'links.json')}: {e}"
                )
                raise e

            logger.info(f"Downloading {len(links)} webpages")
            for link in tqdm(links, desc="Links"):
                while True:
                    try:
                        response = client.get(link)
                        break
                    except Exception:
                        sleep(urand(0, _SLEEP))
                        continue
                folder = os.path.join(
                    _HTML_OUT_FOLDER,
                    *str(httpx.URL(link).params).split("&"),
                )
                os.makedirs(folder, exist_ok=True)
                with open(os.path.join(folder, "index.html"), "w") as f:
                    f.write(BeautifulSoup(response.text, _PARSER).prettify())


if __name__ == "__main__":
    args = cli_args()
    main(args)
