# Interactive shell setup for the dev container: the same coloured prompt as the host
# (user@host:dir (branch)$), where the host name is the container's.
parse_git_branch() {
  local branch
  branch="$(git branch --show-current 2>/dev/null)"
  [ -n "$branch" ] && printf ' (%s)' "$branch"
}

PS1='\[\033[01;32m\]\u@\h\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\]\[\033[01;33m\]$(parse_git_branch)\[\033[00m\]\$ '
alias ls='ls --color=auto'
alias grep='grep --color=auto'
