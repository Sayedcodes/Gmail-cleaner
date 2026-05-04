
import base64
import json
import os
import threading
import time
import uuid
from functools import wraps

os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

from flask import Flask, Response, jsonify, redirect, render_template_string, request, session, url_for
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import BatchHttpRequest
from werkzeug.middleware.proxy_fix import ProxyFix


SCOPES = ["https://mail.google.com/"]
JOBS = {}
JOBS_LOCK = threading.Lock()

ICON_192_B64 = "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"
ICON_512_B64 = "iVBORw0KGgoAAAANSUhEUgAAAgAAAAIACAYAAAD0eNT6AAAkY0lEQVR4nO3de7ReVXkv4HeTbPZOgCQguV+QBAIEOBCogBcIQS4CKioQUdsiBYXjfdRWex3nqOVYtbTWgcpFKSLa2oE6QIUgiNxEBYJCQgIJBIgJYICEBEl29iZw/qARCDvJvsz1rct8njH6R2s6v7WX35rvb71zrm+1jdx57AsBAGRlu7IPAABoPQEAADIkAABAhgQAAMiQAAAAGRIAACBDAgAAZEgAAIAMCQAAkCEBAAAyJAAAQIYEAADIkAAAABkSAAAgQwIAAGRIAACADAkAAJAhAQAAMiQAAECGBAAAyJAAAAAZEgAAIEMCAABkSAAAgAwJAACQIQEAADIkAABAhgQAAMiQAAAAGRIAACBDAgAAZEgAAIAMCQAAkCEBAAAyJAAAQIYEAADIkAAAABkSAAAgQwIAAGRIAACADAkAAJChoWUfANU0Y9XGsg8BSGjhLkPKPgQqpm3kzmNfKPsgKIciD0QIB7kSADKh2AP9IRQ0nwDQUAo+kJJA0DwCQIMo+kArCAPNIADUmIIPVIFAUE8CQA0p/EAVCQL1IgDUhKIP1IkwUH0CQMUp/ECdCQLVJQBUlMIPNIkgUD0CQIUo+kAOhIFqEAAqQOEHciQIlMvLgEqm+AO5Mv+VSwegJL74AC/RDWg9AaDFFH6ALRMEWkcAaBGFH6DvBIHi2QPQAoo/QP+YN4unA1AgX2CAwdMNKIYAUJAmFP+lE0eWfQhAAlNXrCn7EAZNCEhPAChA3Yq/Qg95qlswEALSEgASqkPhV+yBralDKBAE0hAAEqlq8VfwgcGoaiAQAgZPAEigasVf0QeKULUwIAQMjgAwCFUq/Io+0EpVCgOCwMAIAANUleKv8ANlqkoQEAL6TwAYgCoUf4UfqJIqBAEhoH8EgH4qs/gr+kAdlBkGhIC+EwD6oazir/ADdVRWEBAC+sa7APpI8Qfon7Lmryos09aBDkAflPFlUviBJimjG6ATsHUCwDa0uvgr/ECTtToICAFbZglgKxR/gLRaPc9ZDtgyHYAtaOWXRuEHctTKboBOwKvpAPRC8QcoXivnP52AV9MB2EyrviQKP8BLWtUN0Al4iQ7Ayyj+AOVo1byoE/ASAeB/KP4A5RICWssSQLTmy6DwA/RdK5YEcl8O0AFoAcUfoH/Mm8XLPgAUfffvSwwwMEXPn7kvBWQdABR/gGoTAoqTbQBQ/AHqQQgoRrYBoEiKP0Ba5tX0sgwARaY9X1KAYhQ5v+bYBcguACj+APUlBKSTVQBQ/AHqTwhII6sAUBTFH6C1zLuDl00AKCrV+RIClKOo+TeXLkAWAUDxB2gmIWDgsggAAMArNT4AuPsHaDZdgIFpfAAoguIPUC3m5f5rdAAoIr35kgFUUxHzc5O7AI0OAABA7xobANz9A+RHF6DvGhkAFH+AfAkBfdPIAAAAbF3jAoC7fwB0AbatcQEgNcUfoJ7M31snAABAhhoVAFK3Z6RHgHpLPY83aRmgUQEAAOibxgQAd/8A9EYXoHeNCQApKf4AzWJef7VGBICmpDEA6qEJdacRASAlKRGgmczvryQAAECGah8AmtCGAaB+6l5/ah8AUtIeAmg28/xLah0A6p6+AKi3OtehWgeAlKRCgDyY718kAABAhgSAkAYBcmPer3EAqPO6CwDNUdd6VNsAAAAMXPYBQBsIIE+5z/+1DAB1bbcA0Ex1rEu1DAAAwOBkHQByb/8A5C7nOpB1AACAXNUuANRxnQWA5qtbfapdAAAABi/bAJDzug8AL8m1HmQbAAAgZwIAAGSoVgGgbhssAMhLnepUrQIAAJBGlgEg1w0fAPQux7qQZQAAgNwJAACQIQEAADIkAABAhmoTAOr0aAUA+apLvapNAEglx52eAGxbbvUhuwAAAAgAAJAlAQAAMiQAAECGBAAAyJAAAAAZEgAAIEMCAABkSAAAgAwJAACQIQEAADIkAABAhgQAAMiQAFBxU1esKfsQAPrN3FV9Q8s+ALZt04WU26sqgfpR+OtDB6DCNr+Qpq5Y4+ICKqm3+cl8VW0CQA25qIAqMSfVkwBQUdu6oHQDgLL1ZR4yT1WXPQA1t7X9AS48IIXN5xdzSzMIABU0kIvLBQkUZbDzy9QVa2xiriBLAACQIQGgYtzJA01kbqseSwAVs6lN5mIBmkL7v5oEgIoSBIC6U/irzRJAxbmAgDoyd1WfAFADSyeOdDEBtWG+qgcBAAAyJADUhL0AQF2Yr+pBAKgBFxNQN+at6vMUAK8yf+ftyz4EILH9V3eXfQhUjA5AxZWRovdf3W2ygIYo83rWBag2AaCBUt3BCwJQXymv3/k7b68z2EACQIUNJD1vukhTXqyCANRLyuv15XPJQOYVXYDqEgAaZPOLM3VqFwKg2lpx168T0Bw2ATbE1i7KTf9Ziolh0xgmAaiOou74t/Zv3BDUnwBQUUW0zQQBaJZWF/6BmrpijV8HrCBLAA3Q3ws35dKA/QFQjrKLv/BffwJAxuwPgPqxu59ULAFkzrIA1EPZd/w0jwBARAgCUFUKP0WxBMAr2B8A1aH4UyQdAHqV8jEfHQHoH4WfVhAA2KKUywKbxjEZwZYp/LSSAMA22R8AxVL4KYMAQJ8JApBW6j0yrif6wyZA+s2LhmDwUt/1K/70lw4AA2J/AAyMdj9VIQAwKJYFoG8UfqpGACAJQQB6Z52fqhIASEoQgJe466fKbAKkEF40RM68sIc60AGgMLoB5MYdP3UiAFA4QYCmU/ipI0sAtIwXDdFEij91pQNAy3nREE2g8FN3AgCl8ENC1JXCT1MIAJTK/gDqQuGnaewBoBLsD6DKFH+aSAeASrE/gCpR+GkyAYDKsT+Asin85EAAoLLsD6DVFH5yYg8AlWd/AK2g+JMbHQBqQ0eAIij85EoAoHZsFCQFhZ/cCQDUko2CDJTCDy+yB4Basz+A/lD84SU6ADSC/QFsjcIPryYA0Cj2B/ByCj9smQBA49gfgMIP22YPAI1lf0CeFH/oGx0AGs/+gDwo/NA/AgDZEASaSeGHgbEEQHZSTvKWBcqTclkm5XIR1IUOAFnSDaiv1KHLf2/kSgAga4JAvWj3QzoCAIQgUHUKP6QnAMDL+CGhalH4oTg2AcJmUm8Is1Gw/1L/7oLiD6+mAwBbYFmgHAo/tIYAANsgCLSGwg+tJQBAH9kfUAyFH8ohAEA/eNFQOgo/lMsmQBgALxoaHMUfyqcDAINgf0D/KPxQHQIAJCAIbJ3CD9VjCQAS8vsBr+SFPVBdAgAkZn/Ai9z1Q7VZAoCC5LosoPBDPQgAULBcgoDCD/UiAECLNPWHhBR+qCd7AKCFmvaiIcUf6ksHAEpQ92UBhR/qTwCAEtUtCCj80BwCAFRA1fcHKPzQPPYAQEVUdX+A4g/NJABAYoMtmFX5IaEq/Ypf2ZsdoYksAUAiqYtUWfsDqnrHX6VHH6EJBAAYpN4K5v6ru5MVqlYFgaoX/s3/d0EABscSAAxQq3+nvxVFNYVWFeY6vycBqkAHAAagL4UnZRdgkyK6AakUUfjLOs+QAwEA+qEqd5wpg8BgVaH4WhaA/hMAoA8Gs5O+yKJUZhAoutgO5G8SBKDv7AGArajLOnOrC17VC2xd/nuDMukAQC9SFo9WrVG3ohvQyg1+KcepemCBMggA8DJ12BjX18+s487+zT9PEIDiCAAQzSj8WzqGrf1t23oHQdl/hyAAxbEHgOylvlOuWnEZ6PFU6e+o6nsSoM4EALKVeqNYlQrm5noroJv+997+71X9W1KHAEGAnFkCIDtNbPf31dZa6nX5OywLQBoCANnIufBvbkvdgDoRBGBwBAAaT+FvNkEABkYAoLEU/rwIAtA/NgHSSE3f2c+WeWIA+kYHgEbJZVc/21bEmxN9J2gSHQAaIadH+ugfjw5C73QAqDXr/PSF/QHwagIAtaTwMxCCALxEAKBWFH5SEARAAKAmFH6KIAiQM5sAqTyP9FE0jw6SIwGAyrKzn1bzxAA5sQRA5Wj3UybLAuRCAKAyFH6qRBCg6QQASqfwU2WCAE0lAFAahZ86EQRoGgGAllP4qTNBgKbwFAAt5ZE+msKjg9SdAEBLeKSPpvLoIHVlCYBCafeTA8sC1JEAQCEUfnIkCFAnAgBJKfwgCFAPAgBJKPzwaoIAVSYAMCgKP2ybIEAVeQqAAfNIH/SPRwepEgGAfvNIHwyORwepAksA9Jl2P6RjWYCyCQBsk8IPxREEKIsAwBYp/NA6ggCtJgDwKgo/lEcQoFUEAP5I4YfqEAQomqcAiAiP9EFVeXSQoggAmfNIH9SDRwdJzRJAprT7oX4sC5CSAJAZhR/qTxAgBQGgAfZf3b3NC1fhh+YpMwhYQqg/AaCilk4cGVNXrBn0OAo/NF/VOwJLJ45MMg5p2QTYEL1d+Hb2Q15a9cSAu/9m0AFokE1LAXb1Q95SdgQ27wYo/s2hA1BhA2mbKf7AJlV4dFD7v7p0AHgVhR+aw507W6IDUHGtTM/W+aG5yri+3f1Xmw4Af+QOASAfOgA1IEUDdWPeqj4BAICkFP96sARQcSl+DAiglTbNW4JAtQkAFaXwA3UnCFSbAFAxCj/QNIJANdkDUDEuEKCJzG3VIwAAQIYEgAqSlIEmMadVkz0ANbf5hWUPAVCkl8855pt6EwAqaunEkdu8uHpL1S5OILUt3cEPdJ6iGgSAGurrBeXCA4q2aZ5xw1E/9gBU2OYFfOnEkYo6UEm9zU/mq2rTAagBFxFQFzoC9aEDUHGKP1BH5q7qEwAAIEMCAABkSAAAgAwJAACQIQEAADIkAABAhgQAAMiQAAAAGRIAACBDAgAAZEgAAIAMCQAAkCEBAAAyJAAAQIYEAADIkAAAABkSAAAgQwIAAGRIAACADAkAAJAhAQAAMiQAAECGBAAAyJAAAAAZEgAAIEMCAABkSAAAgAwJAACQIQEAADIkAABAhgQAAMiQAAAAGRIAACBDAgAAZEgAAIAMCQAAkCEBAAAyJAAAQIYEAADIkAAAABkSAAAgQwIAAGRIAACADAkAAJAhAQAAMjS07AOAJmlvb4/p0/eMvfaaHuPHj4tx4zb9z5jYcccdo6OjMzo7O6OzsyO23377eO6556K7uzt6enpi3br18fTTq2P16qfj6aefjkcffTxWrFgRy5eviIcffjgeeWRZPP/882X/iS0zefLk2G+/GTFp0sQYP358jB8/LsaPHx8jRoyIzs6O6OwcFp2dHdHe3h49PT2xYcOG6OraEKtWrYqnnnoqVq58Ih55ZFk89NDD8eCDD8bixUti48aNZf9ZUBkCAAzCLrvsErNmHR6HHXZozJixT0yfvmcMHdr3y6q9vT3a29sjImLUqFExYcL4Lf7brq6uWLLkgbjvvvvjrrt+E3feOS+WLn1o0H9DFWy33XYxc+aBceSRs+KAA/aP/fbbL0aOHNHn//+Ojo7o6OiIESMixowZ3eu/6erqigUL7o277vpN3HLLL+KOO+6Mnp6eVH8C1E7byJ3HvlD2QfTFjFVpkvvSiSOTjEO+dtttSpx00ttj9uxZsf/++0VbW1tpx7Jq1aq47bZfxs9/flPcdNMtsXr16tKOpb+GDBkSs2fPire85biYPXtWjBo1qqWfv27d+rj11lvjxz++Jm644YZYv76rpZ9PNU1dsSbJOAt3GZJknCIJANAH7e3tceyxx8R73jMnDjvs0FKL/pY8//zzMW/eXXHllT+Ka66ZG08/nWYiS23MmNExZ86p8Z73zIlx48aVfTgR8WIY+MlPro7vfOc/Y/78BWUfDiUSACpIAKAM7e3tcdppc+JDHzpni63lKurp6YkbbrgxLr/8u3Hbbb8s+3AiImL06F3jox/9cLz73af2a5mk1e6++5644IKL47rrro8XXqjF9EhCAkAFCQC0UltbW5x88jvjYx/7SEycOKHswxmUBx9cGv/4j/83fv3r20v5/B122CHOPvusOOOM98fw4cNKOYaBWLLkgfjoRz8RS5Y8UPah0EI5BYDqxnAoyZQpU+ILXzg3DjnkdWUfShLTpk2NmTMPLCUAHHro6+KLX/znmDRpYss/e7D23HOP2GOPaQIAjSUAwP9oa2uL00//s/irv/rLGDass+zDqbWOjo745Cc/EWeccXpst52fG4EqEgAgIoYN64zzzvtSHHfcMWUfSu3tuutr4qKLvh4HHPC/yj4UYCsEALI3bty4uPjir8WMGTPKPpTa23PPPeIb37iwli1/yI0AQNamTZsal1/+rVrt8K+qmTMPjP/4j4tjp512KvtQgD6wOEe2pkyZEt/+9qWKfwL77LN3XHLJRYo/1IgAQJYmTBgfl19+aYwdO6bsQ6m93Xd/bXzrW9+MESP6/tO9QPkEALLT2dkZF198Qe2f76+CnXbaKS655KJ4zWteU/ahAP1kDwDZ+exn/0/svfdeLfu87u7uuPfeRTF//oJYtGhRPProo/HYY4/H6tVPR1dXV2zYsCGGDBnyx7cE7rLLLjFmzJgYN25s7L77a2OvvabHXntNr8zP5r7cP//zuTFlypSWfFZPT0/Mn78g5s27KxYtui9+97vl8eijj8Wzzz4b69ati+222y46Oztj2LDO2HXX0TFhwviYOHFCzJixT+y3376x5557xJAh1f9xFmgVAYCszJlzSpx88jsL/5yenp6YO/enMXfutXHzzbfGunXrtvrvN27cGN3d3bF2bcTKlU/Efffd/6p/M2bM6DjkkEPi0ENfF4cf/saYPHlyUYffJ3/+538ab3nLsYV/zh133BlXXPGD+OlPr4+1a9du8d9t3Lgxenp64plnnomVK5+IhQsXvuI/33HHHeONb3x9HHHE4XHcccfEzjvvXPShQ6X5KWCyMXbs2Lj++mti+PDhhX3GunXr4hvfuCS+853/jCeffKqwz4l4cePdscceHSeeeEJMmzZ1q//2S1/617jggouSffbkyZPi2mt/Eh0dHcnG3NyvfvXrOO+8L8ddd/0m+dhDhw6N2bOPjDlzTonZs2dt8eVOH/nIx+Oaa65N/vlUl58Chgb6+7//m0KL//e//8P44hf/pfDCv8miRffFokX3xb//+/lx8MEHxbvffWqccMLxLfkVw3/4h78trPivWbM2Pve5c+OHP7yykPEjIp577rm47rrr47rrro9p06bG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"

CATEGORIES = {
    "promotions": {
        "label": "Promotions",
        "query": "category:promotions OR label:promotions",
    },
    "newsletters": {
        "label": "Newsletters",
        "query": (
            "unsubscribe OR from:newsletter OR from:noreply OR from:no-reply "
            "OR subject:newsletter OR subject:digest OR subject:weekly"
        ),
    },
    "jobs": {
        "label": "Job Emails",
        "query": (
            "from:indeed.com OR from:linkedin.com OR from:shine.com "
            "OR from:internshala.com OR from:naukri.com "
            "OR subject:\"job alert\" OR subject:hiring OR subject:openings"
        ),
    },
    "social": {
        "label": "Social Notifications",
        "query": (
            "category:social OR from:notifications OR from:noreply@linkedin.com "
            "OR from:twitter OR from:facebook"
        ),
    },
    "orders": {
        "label": "Orders & Receipts",
        "query": (
            "subject:order OR subject:receipt OR subject:invoice "
            "OR subject:payment OR subject:\"your purchase\""
        ),
    },
    "spam": {
        "label": "Spam",
        "query": "in:spam",
    },
}

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)


BASE_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Gmail Cleaner</title>
  <meta name="theme-color" content="#0f1117">
  <link rel="manifest" href="{{ url_for('manifest') }}">
  <link rel="icon" href="{{ url_for('icon_192') }}">
  <link rel="apple-touch-icon" href="{{ url_for('icon_192') }}">
  <style>
    body {
      margin: 0;
      font-family: Arial, Segoe UI, sans-serif;
      background: #0f1117;
      color: #f5f5f5;
      padding: 24px;
    }
    .box {
      max-width: 900px;
      margin: 0 auto 18px;
      background: #171a23;
      border: 1px solid #2b3242;
      border-radius: 18px;
      padding: 22px;
      box-shadow: 0 18px 45px #0006;
    }
    h1 { margin: 0; font-size: 34px; }
    h2 { margin-top: 0; }
    p { color: #b9c0d0; line-height: 1.55; }
    .btn {
      display: inline-block;
      border: 0;
      border-radius: 12px;
      padding: 12px 16px;
      background: #8b5cf6;
      color: white;
      text-decoration: none;
      font-weight: 700;
      cursor: pointer;
      margin: 4px 6px 4px 0;
    }
    .btn2 { background: #252b3b; }
    .danger { background: #ef4444; }
    .ok { background: #22c55e; color: #07130b; }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 10px;
    }
    .opt {
      background: #202637;
      border: 1px solid #343b4e;
      border-radius: 13px;
      padding: 13px;
      display: flex;
      gap: 10px;
      align-items: center;
    }
    input, textarea {
      width: 100%;
      box-sizing: border-box;
      margin-top: 7px;
      background: #0c101a;
      color: white;
      border: 1px solid #343b4e;
      border-radius: 10px;
      padding: 11px;
    }
    input[type=checkbox], input[type=radio] {
      width: auto;
      margin: 0;
    }
    code {
      white-space: pre-wrap;
      display: block;
      background: #0b0f18;
      border: 1px solid #343b4e;
      border-radius: 10px;
      padding: 12px;
      overflow-wrap: anywhere;
    }
    .msg {
      max-width: 900px;
      margin: 0 auto 18px;
      border-radius: 14px;
      padding: 14px;
      background: #121827;
      border-left: 4px solid #8b5cf6;
    }
    .row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }
    .progress-shell {
      background: #070b13;
      border: 1px solid #343b4e;
      border-radius: 999px;
      overflow: hidden;
      height: 32px;
      position: relative;
      margin: 16px 0;
    }
    .progress-fill {
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, #16a34a, #39ff14);
      transition: width .4s ease;
    }
    .progress-label {
      position: absolute;
      inset: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 800;
      color: #f7fee7;
      text-shadow: 0 1px 4px #000;
    }
    .stats {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(145px, 1fr));
      gap: 10px;
      margin-top: 12px;
    }
    .stat {
      background: #202637;
      border: 1px solid #343b4e;
      border-radius: 13px;
      padding: 12px;
    }
    .stat span {
      color: #b9c0d0;
      display: block;
      font-size: 13px;
    }
    .stat b {
      display: block;
      font-size: 23px;
      margin-top: 6px;
    }
    .terminal {
      background: #020617;
      color: #39ff14;
      border: 1px solid #1f2937;
      border-radius: 12px;
      padding: 14px;
      margin-top: 14px;
      font-family: Consolas, Monaco, monospace;
      min-height: 54px;
      line-height: 1.45;
    }
    .footer {
      max-width: 900px;
      margin: 8px auto 0;
      padding: 14px 6px;
      color: #8f98ad;
      text-align: center;
      font-size: 14px;
      letter-spacing: .2px;
    }
    .footer b {
      color: #f5f5f5;
    }
    .footer .dot {
      color: #39ff14;
      font-weight: 900;
      margin: 0 6px;
    }
    @media(max-width:700px) {
      .row { grid-template-columns: 1fr; }
      body { padding: 12px; }
    }
  </style>
</head>
<body>
  {% if msg %}
    <div class="msg">{{ msg }}</div>
  {% endif %}

  <div class="box">
    <h1>Gmail Cleaner</h1>
    <p>Emails are moved to Trash, not permanently deleted (recoverable within 30 days).</p>
    {% if email %}
      <p>
        Logged in: <b>{{ email }}</b>
        <a class="btn btn2" href="{{ url_for('logout') }}">Logout</a>
      </p>
    {% endif %}
  </div>

  {{ body | safe }}

  <footer class="footer">
    Developed by <b>Sayed Hamza</b><span class="dot">•</span> Gmail Cleaner
  </footer>

  <script>
    if ("serviceWorker" in navigator) {
      window.addEventListener("load", function () {
        navigator.serviceWorker.register("{{ url_for('service_worker') }}")
          .catch(function (error) {
            console.log("Service worker registration failed:", error);
          });
      });
    }
  </script>
</body>
</html>
"""


def render_page(body_template, msg=None, **context):
    body = render_template_string(body_template, **context)
    return render_template_string(
        BASE_HTML,
        body=body,
        email=session.get("email"),
        msg=msg,
    )


def base_url():
    configured_url = (
        os.environ.get("PUBLIC_BASE_URL")
        or os.environ.get("RENDER_EXTERNAL_URL")
        or request.host_url
    )
    return configured_url.rstrip("/")


def callback_url():
    return base_url() + "/callback"


def client_config():
    raw = os.environ.get("GOOGLE_CREDENTIALS_JSON", "").strip()

    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "GOOGLE_CREDENTIALS_JSON valid JSON nahi hai. "
                "credentials.json ka full content paste karo."
            ) from exc

    if os.path.exists("credentials.json"):
        with open("credentials.json", "r", encoding="utf-8") as file:
            return json.load(file)

    raise RuntimeError(
        "GOOGLE_CREDENTIALS_JSON missing hai. Render Environment me credentials.json ka full content paste karo."
    )


def allowed_emails():
    raw = os.environ.get("ALLOWED_EMAILS", "").strip().lower()
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def credentials_to_dict(credentials):
    return {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
    }


def credentials_from_info(info):
    credentials = Credentials.from_authorized_user_info(info, SCOPES)

    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())

    return credentials


def credentials_from_session():
    info = session.get("credentials")
    if not info:
        raise RuntimeError("Login required")

    credentials = credentials_from_info(info)
    session["credentials"] = credentials_to_dict(credentials)
    return credentials


def gmail_service():
    return build("gmail", "v1", credentials=credentials_from_session(), cache_discovery=False)


def gmail_service_from_info(info):
    return build("gmail", "v1", credentials=credentials_from_info(info), cache_discovery=False)


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "credentials" not in session:
            return redirect(url_for("home"))
        return fn(*args, **kwargs)

    return wrapper


def make_query(form):
    parts = []
    labels = []

    for key in form.getlist("category"):
        if key in CATEGORIES:
            labels.append(CATEGORIES[key]["label"])
            parts.append("(" + CATEGORIES[key]["query"] + ")")

    custom_query = form.get("custom", "").strip()
    if custom_query:
        labels.append("Custom")
        parts.append("(" + custom_query + ")")

    if not parts:
        raise ValueError("Kam se kam ek category ya custom query select karo.")

    query = " OR ".join(parts)
    date_mode = form.get("date_mode", "all")

    if date_mode == "last":
        days = form.get("days", "").strip()
        if not days.isdigit() or int(days) < 1:
            raise ValueError("Last N days me valid number daalo.")
        query = "(" + query + ") newer_than:" + str(int(days)) + "d"

    elif date_mode == "range":
        after_date = form.get("after", "").strip().replace("-", "/")
        before_date = form.get("before", "").strip().replace("-", "/")
        if not after_date or not before_date:
            raise ValueError("From aur To date dono daalo.")
        query = "(" + query + ") after:" + after_date + " before:" + before_date

    return query, labels


def fetch_thread_ids(service, query):
    ids = []
    page_token = None

    while True:
        kwargs = {"userId": "me", "q": query, "maxResults": 500}
        if page_token:
            kwargs["pageToken"] = page_token

        result = service.users().threads().list(**kwargs).execute()
        ids.extend([thread["id"] for thread in result.get("threads", [])])

        page_token = result.get("nextPageToken")
        if not page_token:
            return ids


def update_job(job_id, **updates):
    with JOBS_LOCK:
        if job_id in JOBS:
            JOBS[job_id].update(updates)


def get_job(job_id):
    with JOBS_LOCK:
        return dict(JOBS.get(job_id, {}))


def seconds_to_text(seconds):
    seconds = int(max(0, seconds or 0))
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)

    if hours:
        return f"{hours}h {minutes}m {sec}s"
    if minutes:
        return f"{minutes}m {sec}s"
    return f"{sec}s"


def trash_threads_with_progress(service, ids, job_id):
    """Move Gmail threads to Trash with live progress + safer retry mode.

    Batch size is 10 for maximum safety.
    Failed requests are retried up to 5 times before being counted as failed.
    """
    total = len(ids)
    batch_size = 10
    max_retries = 5

    update_job(
        job_id,
        total=total,
        status="running",
        message=f"Deleting started... Batch size: {batch_size}, retries: {max_retries}",
    )

    if total == 0:
        update_job(
            job_id,
            status="done",
            percent=100,
            message="No matching emails found.",
            finished_at=time.time(),
        )
        return

    def update_progress_message(extra_message=""):
        job = get_job(job_id)
        done = int(job.get("done", 0))
        failed = int(job.get("failed", 0))
        processed = done + failed
        elapsed = max(0.1, time.time() - float(job.get("started_at", time.time())))
        speed = round(processed / elapsed, 2) if processed else 0
        remaining = max(0, total - processed)
        eta_seconds = int(remaining / speed) if speed > 0 else 0
        percent = round((processed / total) * 100, 1) if total else 100
        filled = min(20, int(percent / 5))

        message = (
            f"[{'█' * filled}{'░' * (20 - filled)}] "
            f"{percent}% | {processed}/{total} | Speed: {speed}/sec | "
            f"ETA: {seconds_to_text(eta_seconds)} | Failed: {failed}"
        )
        if extra_message:
            message += f" | {extra_message}"

        update_job(
            job_id,
            processed=processed,
            percent=percent,
            speed=speed,
            eta=eta_seconds,
            eta_text=seconds_to_text(eta_seconds),
            message=message,
        )

    def trash_chunk(chunk, attempt):
        successful_ids = []
        failed_ids = []

        def callback(request_id, response, exception):
            if exception is None:
                successful_ids.append(request_id)
            else:
                failed_ids.append(request_id)

        batch = BatchHttpRequest(
            callback=callback,
            batch_uri="https://gmail.googleapis.com/batch/gmail/v1",
        )

        for thread_id in chunk:
            batch.add(
                service.users().threads().trash(userId="me", id=thread_id),
                request_id=thread_id,
            )

        try:
            batch.execute()
        except Exception:
            # If the whole batch fails, retry the full chunk.
            failed_ids = list(chunk)
            successful_ids = []

        return successful_ids, failed_ids

    for index in range(0, total, batch_size):
        original_chunk = ids[index:index + batch_size]
        pending = list(original_chunk)

        for attempt in range(1, max_retries + 1):
            if not pending:
                break

            update_progress_message(
                f"Batch {index // batch_size + 1}, attempt {attempt}/{max_retries}"
            )

            successful_ids, failed_ids = trash_chunk(pending, attempt)

            if successful_ids:
                job = get_job(job_id)
                update_job(job_id, done=int(job.get("done", 0)) + len(successful_ids))

            pending = failed_ids

            if pending and attempt < max_retries:
                # Small pause helps Gmail API settle before retry.
                time.sleep(0.8)

        if pending:
            job = get_job(job_id)
            update_job(job_id, failed=int(job.get("failed", 0)) + len(pending))

        update_progress_message()
        time.sleep(0.2)

    job = get_job(job_id)
    done = int(job.get("done", 0))
    failed = int(job.get("failed", 0))
    update_job(
        job_id,
        status="done",
        percent=100,
        eta=0,
        eta_text="0s",
        message=f"Done! {done} threads Gmail Trash me move ho gaye. Failed: {failed}",
        finished_at=time.time(),
    )

def run_trash_job(job_id, query, credentials_info):
    try:
        update_job(job_id, status="scanning", message="Searching matching Gmail threads...")
        service = gmail_service_from_info(credentials_info)
        ids = fetch_thread_ids(service, query)
        update_job(job_id, total=len(ids), message=f"Found {len(ids)} threads. Starting delete...")
        trash_threads_with_progress(service, ids, job_id)
    except Exception as exc:
        update_job(
            job_id,
            status="error",
            message=str(exc),
            finished_at=time.time(),
        )


@app.route("/")
def home():
    if "credentials" in session:
        return redirect(url_for("dashboard"))

    return render_page(
        """
        <div class="box">
          <h2>Connect Gmail</h2>
          <p>Google Cloud me Authorized redirect URI ye add karo:</p>
          <code>{{ callback }}</code>
          <br>
          <a class="btn" href="{{ url_for('login') }}">Login with Google</a>
        </div>
        """,
        callback=callback_url(),
    )


@app.route("/login")
def login():
    flow = Flow.from_client_config(
        client_config(),
        scopes=SCOPES,
        redirect_uri=callback_url(),
    )

    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    session["state"] = state
    return redirect(auth_url)


@app.route("/callback")
def callback():
    try:
        flow = Flow.from_client_config(
            client_config(),
            scopes=SCOPES,
            state=session.get("state"),
            redirect_uri=callback_url(),
        )

        auth_response = request.url
        if auth_response.startswith("http://") and "onrender.com" in auth_response:
            auth_response = auth_response.replace("http://", "https://", 1)

        flow.fetch_token(authorization_response=auth_response)
        credentials = flow.credentials

        service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
        email = service.users().getProfile(userId="me").execute().get("emailAddress", "").lower()

        allow_list = allowed_emails()
        if allow_list and email not in allow_list:
            session.clear()
            return render_page(
                """
                <div class="box">
                  <h2>Access denied</h2>
                  <p>This email is not allowed to use this app.</p>
                  <a class="btn btn2" href="{{ url_for('home') }}">Back</a>
                </div>
                """,
                msg=email + " ALLOWED_EMAILS me nahi hai.",
            )

        session["credentials"] = credentials_to_dict(credentials)
        session["email"] = email
        return redirect(url_for("dashboard"))

    except Exception as exc:
        return render_page(
            """
            <div class="box">
              <h2>OAuth Error</h2>
              <p>Google login complete nahi hua.</p>
              <code>{{ error }}</code>
              <br>
              <a class="btn btn2" href="{{ url_for('home') }}">Try again</a>
            </div>
            """,
            error=str(exc),
            msg="Login failed",
        )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/dashboard")
@login_required
def dashboard():
    return render_page(
        """
        <form class="box" method="post" action="{{ url_for('preview') }}">
          <h2>1) Select categories</h2>
          <div class="grid">
            {% for key, category in categories.items() %}
              <label class="opt">
                <input type="checkbox" name="category" value="{{ key }}">
                {{ category.label }}
              </label>
            {% endfor %}
          </div>

          <h2>2) Custom query optional</h2>
          <textarea name="custom" rows="3" placeholder='Example: from:amazon OR subject:"offer"'></textarea>

          <h2>3) Date filter</h2>
          <div class="grid">
            <label class="opt"><input type="radio" name="date_mode" value="all" checked> No filter</label>
            <label class="opt"><input type="radio" name="date_mode" value="last"> Last N days</label>
            <label class="opt"><input type="radio" name="date_mode" value="range"> Date range</label>
          </div>

          <div class="row">
            <label>Last N days
              <input type="number" name="days" min="1" placeholder="30">
            </label>
            <div></div>
          </div>

          <div class="row">
            <label>From
              <input type="date" name="after">
            </label>
            <label>To
              <input type="date" name="before">
            </label>
          </div>

          <br>
          <button class="btn" type="submit">Preview</button>
        </form>
        """,
        categories=CATEGORIES,
    )


@app.route("/preview", methods=["POST"])
@login_required
def preview():
    try:
        query, labels = make_query(request.form)
        ids = fetch_thread_ids(gmail_service(), query)
        session["last_query"] = query

        return render_page(
            """
            <div class="box">
              <h2>Preview</h2>
              <p>Matched Gmail threads: <b>{{ count }}</b></p>
              <p>Selected: {{ labels | join(', ') }}</p>
              <code>{{ query }}</code>
              <br>

              {% if count > 0 %}
                <form method="post" action="{{ url_for('trash') }}">
                  <input type="hidden" name="query" value="{{ query }}">
                  <button class="btn danger" type="submit">Move {{ count }} threads to Trash</button>
                  <a class="btn btn2" href="{{ url_for('dashboard') }}">Cancel</a>
                </form>
              {% else %}
                <a class="btn btn2" href="{{ url_for('dashboard') }}">Back</a>
              {% endif %}
            </div>
            """,
            count=len(ids),
            labels=labels,
            query=query,
            msg="Preview complete",
        )

    except Exception as exc:
        return render_page(
            """
            <div class="box">
              <h2>Preview failed</h2>
              <code>{{ error }}</code>
              <br>
              <a class="btn btn2" href="{{ url_for('dashboard') }}">Back</a>
            </div>
            """,
            error=str(exc),
            msg="Error",
        )


@app.route("/trash", methods=["POST"])
@login_required
def trash():
    query = request.form.get("query", "")

    if not query or query != session.get("last_query"):
        return redirect(url_for("dashboard"))

    job_id = uuid.uuid4().hex
    credentials_info = dict(session.get("credentials", {}))

    with JOBS_LOCK:
        JOBS[job_id] = {
            "status": "starting",
            "query": query,
            "total": 0,
            "done": 0,
            "failed": 0,
            "processed": 0,
            "percent": 0,
            "speed": 0,
            "eta": 0,
            "eta_text": "--",
            "message": "Starting...",
            "started_at": time.time(),
        }

    worker = threading.Thread(
        target=run_trash_job,
        args=(job_id, query, credentials_info),
        daemon=True,
    )
    worker.start()

    return render_page(
        """
        <div class="box">
          <h2>Deleting in progress</h2>
          <p>Is page ko open rehne do. Progress live update hoti rahegi.</p>

          <div class="progress-shell">
            <div id="bar" class="progress-fill"></div>
            <div id="percent" class="progress-label">0%</div>
          </div>

          <div class="stats">
            <div class="stat"><span>Done</span><b id="done">0</b></div>
            <div class="stat"><span>Total</span><b id="total">0</b></div>
            <div class="stat"><span>Speed</span><b id="speed">0/sec</b></div>
            <div class="stat"><span>ETA</span><b id="eta">--</b></div>
            <div class="stat"><span>Failed</span><b id="failed">0</b></div>
          </div>

          <div id="terminal" class="terminal">Starting...</div>

          <div id="finish" style="display:none;margin-top:16px;">
            <a class="btn ok" href="{{ url_for('dashboard') }}">Clean more</a>
          </div>
        </div>

        <script>
          const progressUrl = "{{ url_for('progress', job_id=job_id) }}";

          async function poll() {
            try {
              const response = await fetch(progressUrl, {cache: "no-store"});
              const data = await response.json();
              const percent = Number(data.percent || 0);

              document.getElementById("bar").style.width = percent + "%";
              document.getElementById("percent").textContent = percent.toFixed(1) + "%";
              document.getElementById("done").textContent = data.done || 0;
              document.getElementById("total").textContent = data.total || 0;
              document.getElementById("failed").textContent = data.failed || 0;
              document.getElementById("speed").textContent = (data.speed || 0) + "/sec";
              document.getElementById("eta").textContent = data.eta_text || "--";
              document.getElementById("terminal").textContent = data.message || "Working...";

              if (data.status === "done" || data.status === "error") {
                document.getElementById("finish").style.display = "block";
                return;
              }
            } catch (error) {
              document.getElementById("terminal").textContent = "Progress read error: " + error;
            }

            setTimeout(poll, 1000);
          }

          poll();
        </script>
        """,
        job_id=job_id,
        msg="Live progress started",
    )


@app.route("/progress/<job_id>")
@login_required
def progress(job_id):
    job = get_job(job_id)
    if not job:
        return jsonify({"status": "error", "message": "Job not found", "percent": 0})
    return jsonify(job)



@app.route("/manifest.json")
def manifest():
    return jsonify(
        {
            "name": "Gmail Cleaner",
            "short_name": "Gmail Cleaner",
            "description": "Move selected Gmail threads to Trash with live progress.",
            "start_url": "/",
            "scope": "/",
            "display": "standalone",
            "orientation": "portrait",
            "background_color": "#0f1117",
            "theme_color": "#0f1117",
            "icons": [
                {
                    "src": "/icon-192.png",
                    "sizes": "192x192",
                    "type": "image/png",
                    "purpose": "any maskable",
                },
                {
                    "src": "/icon-512.png",
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "any maskable",
                },
            ],
        }
    )


@app.route("/service-worker.js")
def service_worker():
    js = """
const CACHE_NAME = "gmail-cleaner-pwa-v1";

self.addEventListener("install", function(event) {
  self.skipWaiting();
});

self.addEventListener("activate", function(event) {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", function(event) {
  event.respondWith(fetch(event.request));
});
"""
    return Response(js, mimetype="application/javascript")


@app.route("/icon-192.png")
def icon_192():
    return Response(base64.b64decode(ICON_192_B64), mimetype="image/png")


@app.route("/icon-512.png")
def icon_512():
    return Response(base64.b64decode(ICON_512_B64), mimetype="image/png")


@app.route("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
