"""Regenerate site/board-data.js and site/media-data.js from the stored databases (no network)."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ai_news_pipeline.board import Store, write_bundle
from ai_news_pipeline.media import MediaStore, write_media


def build_site_data():
    write_bundle(Store().bundle())
    write_media(MediaStore().bundle())


if __name__=='__main__':build_site_data();print('site data rebuilt')
