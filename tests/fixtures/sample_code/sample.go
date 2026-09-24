package main

import (
	"fmt"
	"strings"
)

// Repository represents a code repository.
type Repository struct {
	Name string
	URL  string
}

// FullName returns the formatted repository name.
func (r *Repository) FullName() string {
	return fmt.Sprintf("repo:%s", r.Name)
}

// CleanURL removes trailing slashes from the given URL.
func CleanURL(raw string) string {
	return strings.TrimRight(raw, "/")
}
