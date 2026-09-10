# Add to ~/.config/fish/config.fish: cument shell-init fish | source
if status is-interactive; and not set -q CUMENT_SHELL_LOADED
    set -g CUMENT_SHELL_LOADED 1
    function _cument_prompt --on-event fish_prompt
        command cument context --pid $fish_pid "$PWD" >/dev/null 2>&1 &
        disown $last_pid
    end
    if not set -q CUMENT_TITLE; or test "$CUMENT_TITLE" != 0
        function fish_title
            printf '%s — cument:%s' (string replace -ar '[^[:alnum:]. _-]' '_' -- (basename "$PWD")) $fish_pid
        end
    end
end
