#!/usr/bin/env bash
# Path-only helper for the sandbox's writable mount boundary.
# Return success when a project path overlaps a credential-bearing HOME path.
sadskill_is_root() {
  [[ "$1" == "0" ]]
}


sadskill_is_sensitive_home_mount() {
  local project_dir="$1"
  local user_home="$2"
  local relative protected
  # Reject sensitive path components even when NSS cannot enumerate the owner
  # of a non-current home (for example, an LDAP user while running as root).
  for relative in .ssh .gnupg .aws .azure .kube .docker .config .password-store \
                  .local/share/keyrings .local/share/kwalletd; do
    case "$project_dir" in
      */"$relative"|*/"$relative"/*) return 0 ;;
    esac
    if [[ -d "$project_dir/$relative" ]]; then
      return 0
    fi
  done
  for relative in .ssh .gnupg .aws .azure .kube .docker .config .password-store \
                  .local/share/keyrings .local/share/kwalletd; do
    protected="$user_home/$relative"
    if [[ -d "$protected" ]]; then
      protected="$(cd -- "$protected" && pwd -P)"
    fi
    if [[ "$project_dir" == "$protected" || "$project_dir" == "$protected/"* || \
          "$protected" == "$project_dir/"* ]]; then
      return 0
    fi
  done
  return 1
}

sadskill_path_has_symlink() {
  local path="$1"
  local current="/"
  local component
  [[ "$path" == /* ]] || path="$PWD/$path"
  IFS=/ read -ra components <<< "${path#/}"
  for component in "${components[@]}"; do
    case "$component" in
      ""|.) continue ;;
      ..) return 0 ;;
    esac
    current="${current%/}/$component"
    [[ -L "$current" ]] && return 0
  done
  return 1
}

sadskill_has_sensitive_descendant() {
  local project_dir="$1"
  local find_bin result
  find_bin=""
  for candidate in /usr/bin/find /bin/find; do
    if [[ -x "$candidate" ]]; then
      find_bin="$candidate"
      break
    fi
  done
  # If no trusted find is available, fail closed rather than miss a nested home.
  [[ -n "$find_bin" ]] || return 0
  if ! result="$("$find_bin" "$project_dir" \
      \( -type d -o -type l \) \
      \( -name .ssh -o -name .gnupg -o -name .aws -o -name .azure \
         -o -name .kube -o -name .docker -o -name .password-store \
         -o -name keyrings -o -name kwalletd \
         -o -path '*/.config/gh' -o -path '*/.config/gcloud' \
         -o -path '*/.config/azure' \) -print -quit 2>/dev/null)"; then
    return 0
  fi
  [[ -n "$result" ]]
}
