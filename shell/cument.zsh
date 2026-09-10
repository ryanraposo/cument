# Add to ~/.zshrc: eval "$(cument shell-init zsh)"
if [[ -o interactive && -z ${CUMENT_SHELL_LOADED:-} ]]; then
    CUMENT_SHELL_LOADED=1
    autoload -Uz add-zsh-hook
    _cument_prompt() {
        local result=$?
        if [[ ${CUMENT_TITLE:-1} != 0 ]]; then
            local title=${PWD:t}
            title=${title//[^[:alnum:]. _-]/_}
            printf '\033]0;%s — cument:%s\007' "$title" "$$"
        fi
        command cument context --pid "$$" "$PWD" >/dev/null 2>&1 &!
        return "$result"
    }
    add-zsh-hook precmd _cument_prompt
fi
