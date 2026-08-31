import fitz

from .modified_pdfplumber.page import Page


def extract_page_chars(page: fitz.Page):
    text_page = page.get_textpage()
    char_list = []
    raw_dict_blocks = text_page.extractRAWDICT()['blocks']
    for block in raw_dict_blocks:
        if block['type'] != 0:
            continue
        for line in block['lines']:
            if line['wmode'] == 0:
                upright = True
            else:  # 不去除非竖直文本
                upright = False
            for span in line['spans']:
                font = span['font']
                size = span['size']
                ascender = span['ascender']
                descender = span['descender']
                for char in span['chars']:
                    bottom = char['origin'][1] - size * descender / (ascender - descender)
                    top = bottom - size
                    char_list.append(
                        {'text': char['c'], 'upright': upright, 'fontname': font, 'size': size, 'x0': char['bbox'][0],
                         'x1': char['bbox'][2], 'top': top, 'bottom': bottom})
    # print(char_list)
    return char_list


def group_char_into_word(char_list, y_tolerance=1.2, x_tolerance_rate=0.15, horizontal_ltr=True, vertical_ttb=True):
    def char_begins_new_word(
            prev_char,
            curr_char,
    ) -> bool:

        inter_tol = y_tolerance  # 绝对Tolerance
        intra_tol = x_tolerance_rate * max(curr_char['x1'] - curr_char['x0'],
                                           curr_char['bottom'] - curr_char['top'],
                                           prev_char['x1'] - prev_char['x0'],
                                           prev_char['bottom'] - prev_char['top'])

        if curr_char["upright"]:
            inter_attr = "top"
            intra_attr_min = "x0"
            intra_attr_max = "x1"
            if horizontal_ltr:
                char_min = prev_char
                char_max = curr_char
            else:
                char_min = curr_char
                char_max = prev_char
        else:
            inter_attr = "x0"
            intra_attr_min = "top"
            intra_attr_max = "bottom"
            if vertical_ttb:
                char_min = curr_char
                char_max = prev_char
            else:
                char_min = prev_char
                char_max = curr_char
        return bool(
            # Intraline test
            ((char_max[intra_attr_min] - char_min[intra_attr_max]) > intra_tol)
            # Interline test
            or (abs(char_max[inter_attr] - char_min[inter_attr]) > inter_tol)
        )

    def iter_chars_to_words(
            ordered_chars
    ):
        current_word = []

        def start_next_word(
                new_char,
        ):
            nonlocal current_word
            if current_word:
                yield current_word
            current_word = [] if new_char is None else [new_char]

        for char in ordered_chars:
            text = char["text"]
            if text.isspace():  # 空格切分
                yield from start_next_word(None)
            elif current_word and char_begins_new_word(current_word[-1], char):
                yield from start_next_word(char)
            elif current_word and current_word[-1]['upright'] != char['upright']:
                yield from start_next_word(char)
            elif current_word and current_word[-1]['size'] != char['size']:
                yield from start_next_word(char)
            else:
                current_word.append(char)
        # Finally, after all chars processed
        if current_word:
            yield current_word

    def merge_chars(ordered_chars):
        word = {
            "text": "".join(
                c['text'] for c in ordered_chars
            ),
            "x0": min(c['x0'] for c in ordered_chars),
            "x1": max(c['x1'] for c in ordered_chars),
            "top": min(c['top'] for c in ordered_chars),
            "bottom": max(c['bottom'] for c in ordered_chars),
            "upright": ordered_chars[0]['upright'],
            'fontname': ordered_chars[0]['fontname'],
            'size': ordered_chars[0]['size'],
        }

        return word

    word_list = []

    for word_chars in iter_chars_to_words(char_list):
        word_list.append(merge_chars(word_chars))

    return word_list


def extract_words_from_fitz(page, x_tolerance_rate=0.15, y_tolerance=1.2):
    # fitz中的page类
    assert isinstance(page, (fitz.Page))
    return group_char_into_word(extract_page_chars(page), y_tolerance, x_tolerance_rate)


def extract_words_from_pdfplumber(page, x_tolerance_rate=0.15, y_tolerance=1.2):
    # pdfplumber中的page类
    assert isinstance(page, (Page))
    words = page.extract_words(
        # x_tolerance = x_tolerance,  # 旧版本
        y_tolerance=y_tolerance,
        x_tolerance_rate=x_tolerance_rate,  # 新改动
        keep_blank_chars=False,
        use_text_flow=True,
        horizontal_ltr=True,
        vertical_ttb=True,
        extra_attrs=["fontname", "size", 'upright'],
    )
    return words


if __name__ == '__main__':
    doc = fitz.open('new_test_pdfs/5618d0eebf204fe7eef41540e684585d.pdf')
    x = doc.load_page(12)
    group_char_into_word(extract_page_chars(x))
    # for word in (group_char_into_word(extract_page_chars(x))):
    #     print(word['text'])
