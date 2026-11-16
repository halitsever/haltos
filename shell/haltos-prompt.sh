# HaltOS bash prompt. Sourced from ~/.bashrc.
[ -n "$BASH_VERSION" ] || return 0

__haltos_prompt() {
    local code=$? g='\[\e[38;2;250;250;250m\]' d='\[\e[38;2;113;113;122m\]' \
        r='\[\e[38;2;239;68;68m\]' a='\[\e[38;2;161;161;170m\]' n='\[\e[0m\]'
    local branch status sigil
    branch=$(git symbolic-ref --short HEAD 2>/dev/null || git rev-parse --short HEAD 2>/dev/null)
    [ -n "$branch" ] && branch=" ${d}git:${a}${branch}${n}"
    [ "$code" -ne 0 ] && status=" ${r}[exit ${code}]${n}"
    if [ "$EUID" -eq 0 ]; then sigil="${r}#${n}"; else sigil="${g}\$${n}"; fi
    PS1="\n${d}┌─[${g}\u${d}@${g}\h${d}]─[${g}\w${d}]${n}${branch}${status}\n${d}└─▪${n} ${sigil} "
}
PROMPT_COMMAND="__haltos_prompt${PROMPT_COMMAND:+; $PROMPT_COMMAND}"

# Interactive terminals greet with the OS banner, but nested shells and tmux panes stay quiet.
if [ -z "$HALTOS_GREETED" ] && [ -z "$TMUX" ] && command -v fastfetch >/dev/null; then
    export HALTOS_GREETED=1
    fastfetch
fi
