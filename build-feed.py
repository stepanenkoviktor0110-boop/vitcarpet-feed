# -*- coding: utf-8 -*-
"""Сборка малого курируемого YML-фида по одному разделу vitcarpet.by.

Раздел: «Хит-сет» (тканые ковры) — 11 коллекций.
Цен на сайте нет, поэтому вариант B из 04-feeds §21.4: <price> не ставим вовсе.
Остальные поля карточки (currencyId RUB, vendor, vendorCode, quantity, picture, url)
обязательны — без них карточка в виджете ломается или не рисуется.

Ключевое для рендера (04-feeds §21.3): в <description> обязана быть строка-триггер
"Карточка: [Название](ссылка)". Без неё бот отвечает прозой и карточка не появляется
(проверено на avtosteklo40: фид без триггера → 0 карточек).
"""
import re, sys, time, urllib.request
from xml.sax.saxutils import escape

BASE = 'https://vitcarpet.by'
GROUP = '/catalog/khit-set/'
GROUP_RU = 'Хит-сет'
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
      'Accept': 'text/html,application/xhtml+xml',
      'Accept-Language': 'ru-RU,ru;q=0.9'}

SYNONYMS = ('ковёр, ковер, тканый ковер, ворс хит-сет, термофиксированная нить, '
            'ковер в гостиную, ковер в спальню, ковер на пол, белорусский ковер')


def fetch(url, tries=5):
    """Тянет страницу с ретраями: сайт режет частые последовательные запросы."""
    delays = [0, 2, 5, 9, 15]
    for i in range(tries):
        if delays[i]:
            time.sleep(delays[i])
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode('utf-8', 'replace')
        except Exception as ex:
            print('  повтор %s: %s' % (url, str(ex)[:60]), file=sys.stderr)
    return ''


def text(html):
    html = re.sub(r'(?s)<(script|style).*?</\1>', ' ', html)
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html)).strip()


def parse_group(html):
    items = re.findall(
        r'<div class="goods_item".*?<a href="(/catalog/[^"]+)"></a>.*?<img src="([^"]+)".*?<p class="h4">(.*?)</p>',
        html, re.S)
    return [(u, img, re.sub(r'<[^>]+>', '', t).strip()) for u, img, t in items]


def parse_collection(html, title):
    """Достаёт вводную фразу, характеристики и число расцветок."""
    t = text(html)
    specs = {}
    m = re.search(r'Артикул\s*:\s*(.+?)\s*Ворс\s*:\s*(.+?)\s*Количество ворсовых точек в 1 м²\s*:\s*([\d\s]+?)'
                  r'\s*Высота ворса\s*:\s*(.+?)\s*Вес 1 м² готового изделия\s*:\s*([\d\s]+г)', t)
    if m:
        specs = {'article': m.group(1).strip(), 'pile': m.group(2).strip(),
                 'points': m.group(3).strip(), 'height': m.group(4).strip(), 'weight': m.group(5).strip()}
    lead = ''
    lm = re.search(r'([А-ЯЁ][^.]{20,200}\.)\s*' + re.escape(title), t)
    if lm:
        lead = lm.group(1).strip()
    short = title.replace('Коллекция ', '').strip('«»" ')
    colors = len(set(re.findall(re.escape('«' + short + '»') + r'\s*(\d+\s*[a-zA-Z]\d)', t)))
    return specs, lead, colors


def keep_last_known_good(reason):
    """Источник недоступен (типовое на раннерах GitHub — геоблок RU-сайта).

    Пустой или недособранный фид ломает карточки бота, поэтому оставляем
    последний рабочий feed.xml и выходим успешно, чтобы не валить деплой.
    """
    import os
    print('%s — оставляю прежний feed.xml' % reason, file=sys.stderr)
    sys.exit(0 if os.path.exists('feed.xml') else 1)


def main():
    group_html = fetch(BASE + GROUP)
    items = parse_group(group_html)
    if not items:
        keep_last_known_good('раздел не разобрался')

    offers = []
    for n, (path, img, title) in enumerate(items, start=1):
        url = BASE + path
        html = fetch(url)
        if not html:
            print('  пропуск (не открылась): ' + url, file=sys.stderr)
            continue
        specs, lead, colors = parse_collection(html, title)
        short = title.replace('Коллекция ', '').strip('«»" ')
        art = (specs.get('article') or '').replace(' ', '')
        base_name = 'Ковёр «%s» — тканый, ворс хит-сет' % short
        name = ('%s %s' % (art, base_name)) if art else base_name

        parts = []
        if lead:
            parts.append(lead)
        parts.append('Тканый ковёр из коллекции «%s», раздел «%s».' % (short, GROUP_RU))
        if specs:
            parts.append('Артикул %s. Ворс: %s. Плотность %s ворсовых точек на м². '
                         'Высота ворса %s. Вес 1 м² готового изделия %s.'
                         % (specs.get('article', '—'), specs.get('pile', '—'),
                            specs.get('points', '—'), specs.get('height', '—'), specs.get('weight', '—')))
        if colors:
            parts.append('Расцветок в коллекции: %d.' % colors)
        parts.append('Размеры и цены — в фирменных магазинах и интернет-магазине; '
                     'по опту и расчёту отвечает менеджер.')
        parts.append('Карточка: [%s](%s)' % (name, url))
        parts.append('Запросы: %s, %s.' % (short, SYNONYMS))
        desc = ' '.join(parts)

        offers.append({
            'params': specs,
            'id': 'khitset-%02d' % n,
            'url': url,
            'picture': BASE + img if img.startswith('/') else img,
            'vendor': 'Витебские ковры',
            'vendorCode': (specs.get('article') or short).replace(' ', ''),
            'name': name,
            'description': desc,
        })
        print('  собрал: %s (расцветок %d)' % (name, colors))

    if len(offers) < len(items):
        keep_last_known_good('собрано %d из %d позиций (частичный набор)' % (len(offers), len(items)))

    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<yml_catalog date="%s">' % time.strftime('%Y-%m-%d %H:%M'),
           '  <shop>',
           '    <name>Витебские ковры</name>',
           '    <company>ОАО «Витебские ковры»</company>',
           '    <url>https://vitcarpet.by</url>',
           '    <currencies><currency id="RUB" rate="1"/></currencies>',
           '    <categories><category id="1">Тканые ковры — хит-сет</category></categories>',
           '    <offers>']
    for o in offers:
        out += ['    <offer id="%s" available="true">' % o['id'],
                '      <url>%s</url>' % escape(o['url']),
                '      <currencyId>RUB</currencyId>',
                '      <categoryId>1</categoryId>',
                '      <quantity>1</quantity>',
                '      <picture>%s</picture>' % escape(o['picture']),
                '      <vendor>%s</vendor>' % escape(o['vendor']),
                '      <vendorCode>%s</vendorCode>' % escape(o['vendorCode']),
                '      <name>%s</name>' % escape(o['name']),
                '      <param name="Тип ворса">Хит-сет</param>',
                '      <param name="Материал">%s</param>' % escape(o['params'].get('pile', 'нить ПП')),
                '      <param name="Высота ворса">%s</param>' % escape(o['params'].get('height', '')),
                '      <param name="Плотность">%s ворсовых точек на м²</param>' % escape(o['params'].get('points', '')),
                '      <param name="Тип изделия">Тканый ковёр</param>',
                '      <description>%s</description>' % escape(o['description']),
                '    </offer>']
    out += ['    </offers>', '  </shop>', '</yml_catalog>', '']

    with open('feed.xml', 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(out))
    print('готово: %d офферов в feed.xml' % len(offers))


if __name__ == '__main__':
    main()
