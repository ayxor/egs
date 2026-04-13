document.addEventListener("DOMContentLoaded", () => {
    // Check if we're on the login page
    const loginForm = document.querySelector("#kc-form-login");
    const submitBtnWrapper = document.querySelector("#kc-form-buttons");
    const submitBtn = document.querySelector("#kc-login");

    if (!loginForm || !submitBtnWrapper || !submitBtn) return;

    // Create the wrapper matching the container structure
    const registerWrapper = document.createElement("div");
    registerWrapper.className = submitBtnWrapper.className;
    // Add margin so it doesn't stick to the login button
    registerWrapper.style.marginTop = "0.75rem";

    // Create the 'Create account' button
    const registerBtn = document.createElement("a");
    registerBtn.href = "http://localhost:8091/auth#register";
    registerBtn.innerText = "Create account";
    
    // Copy the original button's classes
    let btnClasses = submitBtn.className;
    
    // If it uses PatternFly 5/4 styles (e.g. pf-v5-c-button pf-m-primary)
    // convert it to secondary control
    btnClasses = btnClasses.replace("m-primary", "m-secondary");
    // If it's PF3/Bootstrap: btn-primary -> btn-default
    btnClasses = btnClasses.replace("btn-primary", "btn-default");

    registerBtn.className = btnClasses;
    // Just force it to behave like a block element, typical for secondary buttons inside the form group
    registerBtn.style.display = "block";
    registerBtn.style.textAlign = "center";
    registerBtn.style.textDecoration = "none";
    
    // Some basic CSS fix to override `a` tag defaults if they look like simple links
    if (btnClasses.includes("pf-")) {
      // PatternFly explicit color overrides just in case standard text color takes precedence
      registerBtn.style.color = "#151515"; 
    }

    registerWrapper.appendChild(registerBtn);
    submitBtnWrapper.parentNode.appendChild(registerWrapper);

    // Hide Keycloak's default registration block if it happens to show up
    const existingReg = document.querySelector("#kc-registration");
    if (existingReg) existingReg.style.display = "none";
});
