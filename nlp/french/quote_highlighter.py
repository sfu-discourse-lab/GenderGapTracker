import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict
 
from dominate import document
from dominate.tags import *


class Highlighter:

    targets = None

    def __init__(self, options: Dict[str, Any]) -> None:
        self.options = options
        self._parse_opts(options)
        self._load_all()
        self.__set_ids()

    def _parse_opts(self, options: dict):
        self.text_base = options["text_base"]
        self.target_base = options["target_base"]
        self.prediction_base = options["prediction_base"]
        self.html_base = options["html_base"]

    def __set_ids(self):
        intersecting_ids = set(self.texts).intersection(set(self.predictions))
        if self.targets:
            intersecting_ids = intersecting_ids.intersection(set(self.targets))
        print(f"Retrieved {len(intersecting_ids)} files")
        intersecting_ids = list(intersecting_ids)
        self.ids = intersecting_ids

    def _load_all(self):
        self._load_text_files()
        if not self.options["no_target"]:
            self._load_target_quotes()
        self._load_predicted_quotes()

    def _load_predicted_quotes(self):
        """Saves dict(id (str): quotes (json))"""
        predictions = {}
        for name in os.listdir(self.prediction_base):
            try:
                idx = name[: -len(".json")]
                pquotes = open(self.prediction_base + name, encoding="mac-roman")
                predictions[idx] = json.load(pquotes)
            except Exception as e:
                print(f"{name}: \n{e}")
                # print(e, traceback.format_exc())
        self.predictions = predictions

    def _load_target_quotes(self):
        """Saves dict(id (str): quotes (json))"""
        targets = {}
        for name in os.listdir(self.target_base):
            try:
                idx = name[: -len(".json")]
                tquotes = open(self.target_base + name, encoding="mac-roman")
                targets[idx] = json.load(tquotes)
            except Exception as e:
                print(f"{name}: \n{e}")
        self.targets = targets

    def _load_text_files(self):
        """Saves dict(id (str): text (str))"""
        texts = {}
        for name in os.listdir(self.text_base):
            try:
                idx = name[: -len(".txt")]
                text = open(self.text_base + name).read()
                texts[idx] = text
            except Exception as e:
                print(f"{name}: \n{e}")
        self.texts = texts

    def _get_quote_dict(self, doc_quotes):
        """Get quote dict indexed by start character.

        Args:
            doc_quotes ([type]): [description]

        Returns:
            {int: int}: {start_char: quote_length}
        """
        quotes = {}
        speakers = {}
        for quote in doc_quotes:
            start_char, end_char = [
                int(r) for r in re.findall("[0-9]+", quote["quote_index"])
            ]
            quotes[start_char] = end_char - start_char
            if "speaker_index" in quote:
                if quote["speaker_index"]:
                    start_char, end_char = [
                        int(r) for r in re.findall("[0-9]+", quote["speaker_index"])
                    ]
                    speakers[start_char] = end_char - start_char
        return quotes, speakers

    def _make_html(self, file_id):
        """Create the HTML file from input txt files, prediction quotes and optionally target quotes. Save as `file_id`.

        Args:
            file_id (str): where to save

        Returns:
            hdoc (HTML file): [description]
        """
        pquotes = self.predictions[file_id]
        pquote_lengths, pspeaker_lengths = self._get_quote_dict(pquotes)
        file_text = self.texts[file_id]
        hdoc = document(title=str(file_id))
        tquote_lengths, tspeaker_lengths = {}, {}
        if not self.options["no_target"]:
            tquotes = self.targets[file_id]
            tquote_lengths, tspeaker_lengths = self._get_quote_dict(tquotes)
        with hdoc.head:
            link(rel="stylesheet", href="style.css")
            meta(http_equiv="Content-Type", content="text/html; charset=utf-8")
        with hdoc:
            with div(
                cls="container",
                style="line-height: 2; font-family: roman; color: rgba(0,0,0,0.5); font-size: 0px;",
            ):
                i = 0
                target_quote_chars_left = 0
                target_speaker_chars_left = 0
                prediction_quote_chars_left = 0
                prediction_speaker_chars_left = 0
                for c in file_text:
                    spanstyle = "font-size: 16px;"
                    if i in tquote_lengths:
                        target_quote_chars_left = tquote_lengths[i]
                    if i in pquote_lengths:
                        prediction_quote_chars_left = pquote_lengths[i]
                    if i in tspeaker_lengths:
                        target_speaker_chars_left = tspeaker_lengths[i]
                    if i in pspeaker_lengths:
                        prediction_speaker_chars_left = pspeaker_lengths[i]
                    if target_quote_chars_left > 0:
                        spanstyle += "font-weight: bold; "
                        target_quote_chars_left -= 1
                    if prediction_quote_chars_left > 0:
                        spanstyle += "background-color: rgba(0,255,0,0.5);"
                        prediction_quote_chars_left -= 1
                    if target_speaker_chars_left > 0:
                        spanstyle += "text-decoration: underline;"
                        target_speaker_chars_left -= 1
                    if prediction_speaker_chars_left > 0:
                        spanstyle += "font-style: italic; color: rgba(0,0,0,1);"
                        prediction_speaker_chars_left -= 1
                    if c == " ":
                        c = "_"
                        spanstyle += "color:rgba(0,0,0,0);"
                    span(c, style=spanstyle)
                    i += 1
        return hdoc

    def write_html(self, file_id):
        Path(self.html_base).mkdir(parents=True, exist_ok=True)
        html = self._make_html(file_id)
        original_stdout = sys.stdout
        out = open(self.html_base + file_id + ".html", "w")
        sys.stdout = out
        print(html)
        out.close()
        sys.stdout = original_stdout

    def highlight(self):
        for idx in self.ids:
            self.write_html(idx)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create HTML file with highlighting for target vs predicted quotes.")
    parser.add_argument("--text-base", default="./data/text/", type=str, help="Where the text which the quotes were extracted from is stored.")
    parser.add_argument("--html-base", default="./data/html/", type=str, help="Where to store the output HTML.")
    parser.add_argument("--target-base", default="", type=str, help="Where the (annotated) target quotes are stored.")
    parser.add_argument("--prediction-base", default="./data/prediction/", type=str, help="Where the predicted quotes are stored.")
    parser.add_argument("--no-target", "-n", dest="no_target", action="store_true", help="Do not highlight target quotes/speakers")

    options = vars(parser.parse_args())

    highlighter = Highlighter(options)
    highlighter.highlight()
