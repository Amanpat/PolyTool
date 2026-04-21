printf '%''s\n' '$ find artifacts/ -maxdepth 3 -type d | sort'
find artifacts/ -maxdepth 3 -type d | sort
printf '\n%''s\n' '$ echo "=== File counts by extension ==="'
echo "=== File counts by extension ==="
printf '%''s\n' '$ find artifacts/ -type f | sed '\''s/.*\.//'\'' | sort | uniq -c | sort -rn | head -20'
find artifacts/ -type f | sed 's/.*\.//' | sort | uniq -c | sort -rn | head -20
printf '\n%''s\n' '$ du -sh artifacts/'
du -sh artifacts/
printf '\n%''s\n' '$ du -sh artifacts/*/'
du -sh artifacts/*/
printf '\n%''s\n' '$ find artifacts/ -type f -exec du -h {} \; | sort -rh | head -30'
find artifacts/ -type f -exec du -h {} \; | sort -rh | head -30
printf '\n%''s\n' '$ grep -i "artifact" .gitignore'
grep -i "artifact" .gitignore
printf '\n%''s\n' '$ git ls-files artifacts/ | head -50'
git ls-files artifacts/ | head -50
printf '\n%''s\n' '$ find artifacts/ -maxdepth 2 | sort'
find artifacts/ -maxdepth 2 | sort