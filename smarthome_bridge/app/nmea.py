def checksum(sentence):
    i = 0
    cs = 0
    sentence = sentence.replace('$', '')
    sentence = sentence.split('*')[0]
    while i < len(sentence):
        cs ^= ord(sentence[i])
        i += 1
    return "%02X" % cs


def add_checksum(sentence):
    sentence += '*' + checksum(sentence)
    return sentence


def compose(header, cmd, params=None):
    if params is None:
        params = []
    sentence = f'${header},{cmd},'
    for param in params:
        sentence += param + ','
    return add_checksum(sentence) + '\n'
