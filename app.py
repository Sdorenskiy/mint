"""MINT — запуск интерфейса:  streamlit run app.py

Вся логика — в пакете mint/ (ядро без Streamlit) и mint/ui/ (страница). Здесь только точка входа.
"""
from mint.ui.app import main

main()
