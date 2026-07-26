from datetime import datetime
import difflib

def ago(timestamp):
    """
    Convert unix time to time ago
    """
    now = datetime.now()
    diff = now - datetime.fromtimestamp(timestamp)
    seconds = diff.seconds
    days = diff.days
    
    if days > 365:
        return f"{days/365:.1f} years ago"
    elif days > 30:
        return f"{days/30:.1f} months ago"
    elif days > 7:
        return f"{days/7:.1f} weeks ago"
    elif days > 0:
        return f"{days:.1f} days ago"
    elif seconds > 3600:
        return f"{seconds/3600:.1f} hours ago"
    elif seconds > 60:
        return f"{seconds/60:.1f} minutes ago"
    else:
        return "just now"


def diff(str1, str2):
    matcher = difflib.SequenceMatcher(None, str1, str2)
    out = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'replace':
            out.append(f'"{str1[i1:i2]}"->"{str2[j1:j2]}"')
        elif tag == 'delete':
            out.append(f'-"{str1[i1:i2]}"')
        elif tag == 'insert':
            out.append(f'+"{str2[j1:j2]}"')

    return ' '.join(out)

    
