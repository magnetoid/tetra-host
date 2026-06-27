package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"strings"
	"time"
)

type Result struct {
	OK            bool   `json:"ok"`
	Action        string `json:"action"`
	ApplicationID string `json:"application_id"`
	Detail        string `json:"detail"`
}

func main() {
	if len(os.Args) != 5 {
		fmt.Fprintln(os.Stderr, "usage: coolify-action-helper <base_url> <token> <application_id> <action>")
		os.Exit(2)
	}
	baseURL := strings.TrimRight(os.Args[1], "/")
	token := os.Args[2]
	applicationID := os.Args[3]
	action := os.Args[4]

	result := Result{OK: false, Action: action, ApplicationID: applicationID}
	if action != "deploy" && action != "restart" {
		result.Detail = "unsupported action"
		printResultAndExit(result, 1)
	}

	url := fmt.Sprintf("%s/api/v1/applications/%s/%s", baseURL, applicationID, action)
	req, err := http.NewRequest(http.MethodPost, url, bytes.NewReader(nil))
	if err != nil {
		result.Detail = err.Error()
		printResultAndExit(result, 1)
	}
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("Accept", "application/json")

	client := &http.Client{Timeout: 20 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		result.Detail = err.Error()
		printResultAndExit(result, 1)
	}
	defer resp.Body.Close()

	result.OK = resp.StatusCode >= 200 && resp.StatusCode < 300
	result.Detail = resp.Status
	if !result.OK {
		printResultAndExit(result, 1)
	}
	printResultAndExit(result, 0)
}

func printResultAndExit(result Result, code int) {
	_ = json.NewEncoder(os.Stdout).Encode(result)
	os.Exit(code)
}
