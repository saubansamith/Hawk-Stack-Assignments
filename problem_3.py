def is_balanced(s):
    stack = []
    for ch in s:
        if ch == '(': 
            stack.append(ch)
        elif ch == ')':
            if not stack:
                return False
            stack.pop()
    return len(stack) == 0
