# Add to ~/.bashrc: eval "$(cument shell-init bash)"
if [[ $- == *i* ]] && [[ -z ${CUMENT_SHELL_LOADED:-} ]]; then
    CUMENT_SHELL_LOADED=1
    _cument_prompt() {
        local result=$?
        if [[ ${CUMENT_TITLE:-1} != 0 ]]; then
            local title=${PWD##*/}
            title=${title//[^[:alnum:]. _-]/_}
            printf '\033]0;%s — cument:%s\007' "$title" "$$"
        fi
        (command cument context --pid "$$" "$PWD" >/dev/null 2>&1 &)
        return "$result"
    }
    if declare -p PROMPT_COMMAND 2>/dev/null | command grep -q 'declare -a'; then
        PROMPT_COMMAND+=(_cument_prompt)
    else
        PROMPT_COMMAND="${PROMPT_COMMAND:+$PROMPT_COMMAND; }_cument_prompt"
    fi
fi
